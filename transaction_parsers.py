from abc import ABC, abstractmethod
from enum import Enum
from typing import IO, Mapping
import pandas as pd
from datetime import datetime

"""

"""
class TransactionParser(ABC):
    @staticmethod
    @abstractmethod
    def parse(transactions: IO) -> pd.DataFrame:
        pass

class FidelityCcTransactionParser():
    @staticmethod
    def parse(transactions: IO) -> pd.DataFrame:
        df = pd.read_csv(transactions, parse_dates=[0], date_format='%Y-%m-%d')
        df = pd.DataFrame(df.rename({'Date': 'date', 'Name': 'description', 'Amount': 'amount'}, axis=1)[['date', 'description', 'amount']])
        df['type'] = 'Fidelity CC'
        return df
TransactionParser.register(FidelityCcTransactionParser)

class BOfACcTransactionParser():
    @staticmethod
    def parse(transactions: IO) -> pd.DataFrame:
        df = pd.read_csv(transactions, parse_dates=[0], date_format='%m/%d/%Y')
        df = pd.DataFrame(df.rename({'Posted Date':'date', 'Payee': 'description', 'Amount': 'amount'}, axis=1)[['date', 'description', 'amount']])
        df['type'] = 'Bank of America CC'
        return df
TransactionParser.register(BOfACcTransactionParser)

class FidelityBaTransactionParser():
    @staticmethod
    def parse(transactions: IO) -> pd.DataFrame:
        df = pd.read_csv(transactions, parse_dates=[0], date_format=' %m/%d/%Y', usecols=range(13))
        df = pd.DataFrame(df.rename({'Run Date': 'date', 'Action': 'description', 'Amount ($)': 'amount'}, axis=1)[['date', 'description', 'amount']])
        df['type'] = 'Fidelity BA'
        return df
TransactionParser.register(FidelityBaTransactionParser)

class ChaseCcTransactionParser():
    @staticmethod
    def parse(transactions: IO) -> pd.DataFrame:
        df = pd.read_csv(transactions, parse_dates=[0], date_format=' %m/%d/%Y')
        df = pd.DataFrame(df.rename({'Transaction Date': 'date', 'Description': 'description', 'Amount': 'amount'}, axis=1)[['date', 'description', 'amount']])
        df['type'] = 'Chase CC'
        return df
TransactionParser.register(ChaseCcTransactionParser)

_parsers = {
    'fidelity-cc': FidelityCcTransactionParser,
    'chase-cc': ChaseCcTransactionParser,
    'fidelity-ba': FidelityBaTransactionParser,
    'bank-of-america-cc': BOfACcTransactionParser
}

def parse_transaction(transaction: IO, transaction_type: str, parsers: Mapping[str, TransactionParser]=_parsers) -> pd.DataFrame:
    parser = _parsers.get(transaction_type)
    if not parser:
        raise ValueError(f'transaction {transaction_type} does not have an implemented parser')
    else:
        return parser.parse(transaction)
