import sys
import asyncio
import logging, logging.config
from dotenv import dotenv_values
import traceback
import urllib3
import requests 

try:
    from kraken.exceptions.exceptions import KrakenExceptions
    from kraken.spot.client import User, Market, Trade, Funding, Staking, KrakenSpotWSClient
except ModuleNotFoundError:
    print('USING LOCAL MODULE')
    sys.path.append('/Users/benjamin/repositories/Trading/python-kraken-sdk')
    from kraken.exceptions.exceptions import KrakenExceptions
    from kraken.spot.client import User, Market, Trade, Funding, Staking, KrakenSpotWSClient

logging.basicConfig(
    format='%(asctime)s %(module)s,line: %(lineno)d %(levelname)8s | %(message)s',
    datefmt='%Y/%m/%d %H:%M:%S',
    level=logging.INFO,
)
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

class TradingBot(KrakenSpotWSClient):
    '''
        Class that implements the trading strategy

        > The on_message function gets all events via the websocket connection
        > decisions can be made based on these events
        > for example placing trades using the self.__trade client
        > do everything you want

        ====== P A R A M E T E R S ======
        config: dict
            bot configuration like: {
                'key' 'kraken-futures-key', 
                'secret': 'kraken-secret-key',
                'products': ['PI_XBTUSD]'
            }
    '''
    def __init__(self, config: dict): 
        super().__init__(key=config['key'], secret=config['secret']) # initialize the KakenFuturesWSClient
        self.__config = config

        self.__user = User(key=config['key'], secret=config['secret'])
        self.__trade = Trade(key=config['key'], secret=config['secret'])
        self.__market = Market(key=config['key'], secret=config['secret'])
        self.__funding = Funding(key=config['key'], secret=config['secret'])
        self.__staking = Staking(key=config['key'], secret=config['secret'])

    async def on_message(self, event: dict) -> None:
        '''receives all events that came form the websocket connection'''
        if 'event' in event:
            if event['event'] == 'heartbeat': return
            if event['event'] == 'pong': return
        elif 'error' in event:
            # handle exceptions/errors sent by websocket connection ...
            pass 

        logging.info(event)
        
        # ... begin implementing your trading strategy here
        # call functions of self.__trade and other clients if conditions met... 
        # try:
        #     print(self.__trade.create_order(
        #         ordertype='limit', 
        #         side='buy', 
        #         volume=2, 
        #         pair='XBTUSD', 
        #         price=12000
        #     ))
        # except KrakenExceptions.KrakenPermissionDeniedError:
        #    # ... handle exceptions
        #    pass

        # The spot websocket client also allow sending orders via websockets
        # this is way faster than using REST endpoints
        # example:
        # await self.create_order(
        #     ordertype='limit',
        #     side='buy',
        #     pair='BTC/EUR',
        #     price=20000,
        #     volume=200
        # )
        # more functions can be found in the documentation at: 
        # https://github.com/btschwertfeger/Python-Kraken-SDK

    # add more functions to customize the bot/strategy
    # ... 

    def save_exit(self, reason: str='') -> None:
        '''controlled shutdown of the bot'''
        logging.warning(f'Save exit triggered, reason: {reason}')
        # save data ... 
        # maybe close trades  ...
        exit(1)


class ManagedBot(object):
    '''Class to manage the trading strategy/strategies

    subscribes to desired feeds, instantiates the strategy and runs until condition met

    ====== P A R A M E T E R S ======
    config: dict
        bot configuration like: {
            'key' 'kraken-futures-key', 
            'secret': 'kraken-secret-key',
            'products': ['PI_XBTUSD]'
        }
    '''

    def __init__(self, config: dict):
        self.__config = config
        self.__tradingStrategy = None
        
    def run(self) -> None:
        if not self.__check_credentials(): exit(1)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            asyncio.run(self.__main())
        except KeyboardInterrupt: pass
        finally: 
            loop.close()
            if self.__tradingStrategy != None:
                self.__tradingStrategy.save_exit(reason='Asyncio loop left')

    async def __main(self) -> None:
        '''
            Instantiates the trading strategy (bot) and subscribes to the 
            desired websocket feeds. While no exception within the strategy occur 
            run the loop.

            This variable exception_occur which is an attribute of the KrakenFuturesWSClient
            can be set individually but is also beeing set to True if the websocket connection 
            has some fatal error. This is used to exit the asyncio loop. 
        '''
        self.__tradingStrategy = TradingBot(config=self.__config)

        await self.__tradingStrategy.subscribe(
            subscription={ 'name': 'ticker' }, 
            pair=self.__config['pairs']
        )
        await self.__tradingStrategy.subscribe(
            subscription={ 'name': 'ohlc', 'interval': 15 }, 
            pair=self.__config['pairs']
        )

        await self.__tradingStrategy.subscribe(subscription={ 'name': 'ownTrades' })  
        await self.__tradingStrategy.subscribe(subscription={ 'name': 'openOrders' })  

        while not self.__tradingStrategy.exception_occur: 
            try:
                # check if bot feels good
                # maybe send a status update every day
                # ...
                pass

            except Exception as e:
                message = f'Exception in main: {e} {traceback.format_exc()}'
                logging.error(message)
                self.__tradingStrategy.save_exit(reason=message)
            
            await asyncio.sleep(6)
        self.__tradingStrategy.save_exit(reason='Left main loop because of exception in bot.')
        return

    def __check_credentials(self) -> bool:
        '''Checks the user credentials and the connection to Kraken'''
        try:
            User(self.__config['key'], self.__config['secret']).get_account_balance()
            logging.info('Client credentials are valid')
            return True
        except urllib3.exceptions.MaxRetryError:
            logging.error('MaxRetryError, cannot connect.')
            return False
        except requests.exceptions.ConnectionError:
            logging.error('ConnectionError, Kraken not available.')
            return False
        except KrakenExceptions.KrakenAuthenticationError:
            logging.error('Invalid credentials!')
            return False

    def save_exit(self, reason: str='') -> None:
        self.__tradingStrategy.save_exit(reason=reason)

def main() -> None:
    bot_config = {
        'key': dotenv_values('.env')['API_KEY'],
        'secret': dotenv_values('.env')['SECRET_KEY'],
        'pairs': ['DOT/EUR', 'XBT/USD']
    }
    managedBot = ManagedBot(config=bot_config)
    try:    
        managedBot.run()
    except Exception:
        managedBot.save_exit(reason=f'manageBot.run() has ended: {traceback.format_exc()}')

if __name__ == '__main__': main()