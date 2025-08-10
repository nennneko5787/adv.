import uuid
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI
from pydantic import BaseModel

MODEL = "gemini-2.5-flash"


class Character(BaseModel):
    name: str
    feeling: str
    favorability: float
    currentLocation: str
    bodyInfo: BodyInfo


class ChatResponse(BaseModel):
    character: Character
    message: str
    choices: List[str]


class AIChatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ai = AsyncOpenAI(
            api_key="paicha_kasudakara_sinde", base_url="https://capi.voids.top/v2/"
        )

    def createEmbed(self, chatResponse: ChatResponse) -> List[discord.Embed]:
        embeds: List[discord.Embed] = []

        embeds.append(
            discord.Embed(
                title="情報",
                description=f"""
                    好感度: {chatResponse.character.favorability * 100}
                    今の気分: {chatResponse.character.feeling}
                    現在地: {chatResponse.character.currentLocation}
                """.replace("    ", ""),
            )
            .set_author(name=chatResponse.character.name)
        )

        if chatResponse.choices:
            formattedChoices = "\n".join(
                f"- :regional_indicator_{chr(97 + i)}: {choice}"
                for i, choice in enumerate(chatResponse.choices)
            )
            embeds.append(
                discord.Embed(title="選択肢一覧", description=formattedChoices)
            )

        embeds.append(discord.Embed(description=chatResponse.message))

        return embeds

    def createResponseView(
        self, chatResponse: ChatResponse, returnCallback, modalCallback
    ) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        for i, choice in enumerate(chatResponse.choices):
            button = discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                emoji=chr(0x1F1E6 + i),
                custom_id=choice,
            )
            button.callback = returnCallback
            view.add_item(button)

        modalButton = discord.ui.Button(
            style=discord.ButtonStyle.blurple,
            label="別の言葉を返す",
            custom_id=str(uuid.uuid4()),
        )
        modalButton.callback = modalCallback
        view.add_item(modalButton)

        return view

    @app_commands.command(
        name="new", description="新しいキャラクターとの会話を開始します。"
    )
    @app_commands.rename(intro="キャラクター説明")
    @app_commands.describe(intro="キャラクターの説明。")
    async def newCommand(self, interaction: discord.Interaction, intro: str):
        await interaction.response.defer()

        messages = [
            {
                "role": "system",
                "content": (
                    "アドベンチャーゲームのように会話を返します。ユーザーからのキャラクター説明は以下のとおりです。\n"
                    f"{intro}\n\nchoicesには私が返すべき会話の選択肢を返してください。\n"
                    "contentにはあなたの文章のみをを返すこと。システムの文章はいりません。\n",
                    "favorabilityは0.0~1.0の間の値を返すこと。",
                    "選択肢は最大24個まで増やすことができます。\nあなたは最初に私に話しかけてください。",
                ),
            }
        ]

        response = await self.ai.chat.completions.parse(
            messages=messages,
            model=MODEL,
            response_format=ChatResponse,
        )
        messages.append(
            {
                "role": "assistant",
                "content": response.choices[0].message.model_dump_json(),
            }
        )

        async def returnResponse(inter: discord.Interaction):
            if interaction.user.id != inter.user.id:
                return

            await inter.response.defer()
            messages.append({"role": "user", "content": inter.data["custom_id"]})

            await inter.edit_original_response(content="生成中...", view=None)
            response = await self.ai.chat.completions.parse(
                messages=messages,
                model=MODEL,
                response_format=ChatResponse,
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": response.choices[0].message.model_dump_json(),
                }
            )

            chatResponse = response.choices[0].message.parsed
            view = self.createResponseView(chatResponse, returnResponse, openModal)
            await inter.edit_original_response(
                content="",
                embeds=self.createEmbed(chatResponse),
                view=view,
            )

        _self = self

        async def openModal(inter: discord.Interaction):
            class Modal(discord.ui.Modal, title="別の言葉を返す"):
                choice = discord.ui.TextInput(label="返す内容")

                async def on_submit(self, modelIntaraction: discord.Interaction):
                    if interaction.user.id != modelIntaraction.user.id:
                        return

                    await modelIntaraction.response.defer()
                    messages.append({"role": "user", "content": self.choice.value})

                    await modelIntaraction.edit_original_response(
                        content="生成中...", view=None
                    )
                    response = await _self.ai.chat.completions.parse(
                        messages=messages,
                        model=MODEL,
                        response_format=ChatResponse,
                    )
                    messages.append(
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.model_dump_json(),
                        }
                    )

                    chatResponse = response.choices[0].message.parsed
                    view = _self.createResponseView(
                        chatResponse, returnResponse, openModal
                    )
                    await modelIntaraction.edit_original_response(
                        content="",
                        embeds=_self.createEmbed(chatResponse),
                        view=view,
                    )

            await inter.response.send_modal(
                Modal(timeout=None, custom_id=str(uuid.uuid4()))
            )

        chatResponse = response.choices[0].message.parsed
        view = self.createResponseView(chatResponse, returnResponse, openModal)

        await interaction.followup.send(
            embeds=self.createEmbed(chatResponse),
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AIChatCog(bot))
