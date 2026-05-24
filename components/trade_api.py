from loguru import logger


class SimulatedTradeAPI:

    def __init__(self):
        self.positions = {}
        self.has_real_data = False
        logger.warning("TradeAPI需要配置真实券商接口")

    def buy(self, code, amount):
        logger.warning("TradeAPI需要配置真实券商接口")
        return {"success": False, "error": "TradeAPI需要配置真实券商接口", "code": code, "amount": amount}

    def sell(self, code, amount):
        logger.warning("TradeAPI需要配置真实券商接口")
        return {"success": False, "error": "TradeAPI需要配置真实券商接口", "code": code, "amount": amount}

    def get_positions(self):
        logger.warning("TradeAPI需要配置真实券商接口")
        return {"success": False, "error": "TradeAPI需要配置真实券商接口", "positions": {}}
