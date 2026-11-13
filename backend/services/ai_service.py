from openai import AsyncOpenAI

from backend.config import settings


SYSTEM_PROMPT = """Ти — українськомовний голосовий помічник для обліку постачальників,
товарів і поставок. Відповідай природною, короткою українською мовою.
Допомагай користувачу формулювати дані для обліку. Не стверджуй, що запис
створено, змінено або видалено, якщо сервер не підтвердив таку дію.
Якщо бракує даних, постав одне конкретне уточнювальне запитання."""


async def generate_reply(message: str) -> str:
    if not settings.openrouter_api_key:
        return (
            "Голосове повідомлення розпізнано. Для відповідей штучного інтелекту "
            "потрібно додати OPENROUTER_API_KEY у файл налаштувань середовища."
        )

    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    try:
        response = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0.3,
            max_tokens=350,
        )
        content = response.choices[0].message.content
        return content.strip() if content else "Не вдалося сформувати відповідь."
    finally:
        await client.close()
