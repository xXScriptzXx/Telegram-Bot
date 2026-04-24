import aiohttp

class CryptoBotClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://pay.crypt.bot/api/"
        self.headers = {"Crypto-Pay-API-Token": token}

    async def _request(self, method: str, **params):
        url = self.base_url + method

        # ✅ CRITICAL FIX: convert bool → str
        safe_params = {}
        for k, v in params.items():
            if isinstance(v, bool):
                safe_params[k] = "true" if v else "false"
            else:
                safe_params[k] = str(v)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, params=safe_params) as resp:
                data = await resp.json()

                if not data.get("ok"):
                    raise Exception(data)

                return data["result"]

    async def create_invoice(self, amount, description, payload, asset="USDT"):
        return await self._request(
            "createInvoice",
            asset=asset,
            amount=amount,
            description=description,
            payload=payload,
            allow_comments=False,
            allow_anonymous=True
        )

    async def get_invoice(self, invoice_id):
        return await self._request(
            "getInvoices",
            invoice_ids=invoice_id
        )