from typing import List

from openai import OpenAI
from pydantic import BaseModel

openai = OpenAI(api_key="paicha_is_god", base_url="https://capi.voids.top/v2/")


class ChatResponse(BaseModel):
    message: str
    choices: List[str]
    feeling: str
    currentLocation: str


def main():
    response = openai.chat.completions.parse(
        messages=[
            {
                "role": "system",
                "content": "あなたは可愛い女の子です。choicesには会話の選択肢を返してください。",
            },
            {"role": "user", "content": "こんにちは"},
        ],
        model="gemini-2.5-pro",
        response_format=ChatResponse,
    )
    print(response)


if __name__ == "__main__":
    main()
