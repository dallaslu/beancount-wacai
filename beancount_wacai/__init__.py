"""挖财 xlsx 文件 importer.
"""
import re
import sys
from openpyxl import load_workbook
from beancount.ingest import importer
from beancount.core import data
from beancount.core.number import D
from pypinyin import lazy_pinyin, Style
from beancount.utils.date_utils import parse_date_liberally


class WacaiImporter(importer.ImporterProtocol):

    def __init__(self, assets_liabilities_map, income_map, expenses_map,
                 currency_map={'人民币': 'CNY', '美元': 'USD'},
                 account_debt='Liabilities:Payable',
                 account_credit='Assets:Receivables',
                 account_reimburse='Assets:Reimburse',
                 expenses_interest='Expenses:Interest',
                 account_ufo='Equity:UFO'):
        """Constructor.
        Args:
          assets_liabilities_map: 挖财账户 -> 资产账户
          income_map: 收入类别 -> 收入账户
          expenses_map: 收入小类 -> 收入账户
          currency_map: 挖财货币 -> currency
          account_debt: 借入、还款
          account_credit: 借出、收款
          account_reimburse: 待报销、已报销
          expenses_interest: 利息支出的 Expenses 账户
        """
        self.assets_map = assets_liabilities_map
        self.income_map = income_map
        self.expenses_map = expenses_map
        self.currency_map = currency_map
        self.account_debt = account_debt
        self.account_credit = account_credit
        self.account_reimburse = account_reimburse
        self.expenses_interest = expenses_interest
        self.account_ufo = account_ufo

        self.unknown_accounts = set()
        self.unknown_expenses = set()
        self.unknown_income = set()

        self.dateutil_kwds = {}

    def name(self):
        return 'wacai'

    def identify(self, file):
        file_name = str(file.name)
        if file_name.endswith('.zip'):
            # TODO unzip
            pass
        if re.match(r'.*[\\/]wacai_\w+账本_\d+_\d+\.xlsx$', file_name):
            return True

    def extract(self, file, existing_entries=None):
        file_name = str(file.name)
        book_name = re.findall(r'_(\w+)账本', file_name)[0]
        if book_name == '日常':
            book_name = None
        else:
            book_name = '-'.join(lazy_pinyin(book_name, style=Style.TONE3, neutral_tone_with_five=True))
        entries = []
        wb = load_workbook(filename=file_name)

        for sheet_name in wb.get_sheet_names():
            sheet = wb.get_sheet_by_name(sheet_name)
            if sheet_name == "转账":
                entries.extend(self.__handle_trans(sheet, file_name, book_name))
            if sheet_name == "收入":
                entries.extend(self.__handle_income(sheet, file_name, book_name))
            if sheet_name == "支出":
                entries.extend(self.__handle_expenses(sheet, file_name, book_name))
            if sheet_name == "收款还款":
                entries.extend(self.__handle_receipt_repayment(sheet, file_name, book_name))
            if sheet_name == "借入借出":
                entries.extend(self.__handle_borrow_lend(sheet, file_name, book_name))
        wb.close()
        sys.stderr.write('Unknown accounts:\n')
        sys.stderr.write('\n'.join(self.unknown_accounts))
        sys.stderr.write('\n')
        sys.stderr.write('\n'.join(self.unknown_income))
        sys.stderr.write('\n')
        sys.stderr.write('\n'.join(self.unknown_expenses))
        sys.stderr.write('\n')
        return entries

    def __get_account(self, s):
        account = self.assets_map.get(s)
        if not account:
            account = 'Assets:Unknown:%s' % s.strip()
            self.unknown_accounts.add(account)
        return account

    def __get_currency(self, s):
        return self.currency_map.get(s, 'UNKNOWN.' + s).strip()

    def __get_income(self, s):
        account = self.income_map.get(s)
        if not account:
            account = 'Income:Unknown:%s' % s.strip()
            self.unknown_income.add(account)
        return account

    def __get_expense(self, s):
        account = self.expenses_map.get(s)
        if not account:
            account = 'Expenses:Unknown:%s' % s.strip()
            self.unknown_expenses.add(account)
        return account

    def __handle_sheet(self, sheet, handler):
        def create_reader(row):
            row_str = str(row)

            def read_value(col):
                value = sheet[col + row_str].value
                if value is None:
                    value = ''
                if isinstance(value, str):
                    value = value.strip()
                else:
                    value = str(value)
                # 替换 ￥ 避免 GBK 错误
                return value.replace('¥', 'CNY')

            return read_value;

        entries = []
        for row in range(2, 999999999):
            read_value = create_reader(row)
            time_str = read_value('A')
            if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', str(time_str)):
                date_str = time_str[0:10]
                time_str = time_str[11:19]
                entry = handler(read_value, parse_date_liberally(date_str, self.dateutil_kwds), time_str, row)
                if entry:
                    entries.append(entry)
            else:
                break
        # sys.stderr.write('load %s entries from sheet %s\n' % (len(entries), sheet.name))
        return entries

    def __handle_receipt_repayment(self, sheet, file_name, book_name):
        def handler(read, date_value, time_value, row):
            record_type = read('B')
            payee = read('C')
            account = read('D')
            amount = read('E')
            interest = read('F')
            narration = read('G')

            if narration == '':
                narration = record_type

            meta = data.new_metadata(file_name, row)
            meta['time'] = time_value
            txn = data.Transaction(meta, date_value, "*", payee, narration,
                                   set(book_name) if book_name is not None else set(), set(), [])
            # TODO Currency
            currency = 'CNY'

            if record_type == "还款":
                txn.postings.append(
                    data.Posting(self.__get_account(account), data.Amount(-D(amount), currency), None, None, None,
                                 None))
                if str(interest) not in ('0.00', '0.0', '0'):
                    txn.postings.append(
                        data.Posting(self.expenses_interest, data.Amount(D(interest), currency), None, None, None,
                                     None))
                txn.postings.append(
                    data.Posting(self.account_debt, None, None, None, None, None))
            else:  # 收款
                txn.postings.append(
                    data.Posting(self.__get_account(account), data.Amount(D(amount), currency), None, None, None, None))
                txn.postings.append(
                    data.Posting(self.account_credit, None, None, None, None, None))

            return txn

        return self.__handle_sheet(sheet, handler)

    def __handle_borrow_lend(self, sheet, file_name, book_name):
        def handler(read, date_value, time_value, row):
            record_type = read('B')
            amount = read('C')
            payee = read('D')
            account = read('E')
            narration = read('F')

            meta = data.new_metadata(file_name, row)
            meta['time'] = time_value
            txn = data.Transaction(meta, date_value, "*", payee, narration.strip(),
                                   set(book_name) if book_name is not None else set(), set(), [])
            # TODO Currency
            currency = 'CNY'

            if record_type == "借出":
                txn.postings.append(
                    data.Posting(self.__get_account(account), data.Amount(-D(amount), currency), None, None, None,
                                 None))
                txn.postings.append(
                    data.Posting(self.account_credit, None, None, None, None, None))
            else:  # 收款
                txn.postings.append(
                    data.Posting(self.__get_account(account), data.Amount(D(amount), currency), None, None, None, None))
                txn.postings.append(
                    data.Posting(self.account_debt, None, None, None, None, None))
            return txn

        return self.__handle_sheet(sheet, handler)

    def __handle_expenses(self, sheet, file_name, book_name):
        def handler(read, date_value, time_value, row):
            cate_a = read('B')
            cate_b = read('C')
            amount = read('D')
            currency = read('E')
            account = read('F')
            project = read('G')
            payee = read('H')
            reimburse_status = read('I')
            members = read('J')
            narration = read('K')

            tags = set(book_name) if book_name is not None else set()
            links = set()

            if project != "日常":
                tags.add('-'.join(lazy_pinyin(project, style=Style.TONE3, neutral_tone_with_five=True)))
            if reimburse_status == "待报销":
                tags.add('Pending')
            if reimburse_status == "待报销" or reimburse_status == "已报销":
                links.add('Reimburse')

            meta = data.new_metadata(file_name, row)
            meta['time'] = time_value
            txn = data.Transaction(meta, date_value, "*", payee, narration.strip(),
                                   tags, links, [])

            if cate_b == '漏记款':
                account_expense = self.account_ufo
            else:
                account_expense = self.__get_expense(cate_b)
            if not re.match(r'自己：\d+\.\d+', str(members)):
                # 有多个成员
                txn.postings.append(
                    data.Posting(self.__get_account(account), None, None, None,
                                 None, None))
                for m in str.split(str(members), "，"):
                    foo = str.split(m, "：")
                    member = foo[0]
                    member_amount = foo[1]
                    meta = data.new_metadata(file_name, row)
                    if member != "自己":
                        meta['member'] = member
                    txn.postings.append(
                        data.Posting(account_expense,
                                     data.Amount(D(member_amount), self.__get_currency(currency)), None, None, None,
                                     meta))
                if reimburse_status == "待报销" or reimburse_status == "已报销":
                    txn.postings.append(
                        data.Posting(account_expense,
                                     data.Amount(-D(member_amount), self.__get_currency(currency)), None, None, None,
                                     None))
                    txn.postings.append(
                        data.Posting(self.account_reimburse,
                                     data.Amount(D(member_amount), self.__get_currency(currency)), None, None, None,
                                     None))
            else:
                txn.postings.append(
                    data.Posting(self.__get_account(account),
                                 data.Amount(-D(str(amount)), self.__get_currency(currency)), None, None,
                                 None, None))
                if reimburse_status == "待报销" or reimburse_status == "已报销":
                    txn.postings.append(
                        data.Posting(account_expense,
                                     data.Amount(D('0'), self.__get_currency(currency)), None, None, None,
                                     None))
                    txn.postings.append(
                        data.Posting(self.account_reimburse, None, None, None, None,
                                     None))
                else:
                    txn.postings.append(
                        data.Posting(account_expense, None, None, None, None,
                                     None))
            return txn

        return self.__handle_sheet(sheet, handler)

    def __handle_income(self, sheet, file_name, book_name):
        def handler(read, date_value, time_value, row):
            cate_a = read('B')
            amount = read('C')
            currency = read('D')
            account = read('E')
            project = read('F')
            payer = read('G')
            narration = read('I')

            tags = set(book_name) if book_name is not None else set()
            links = set()
            if project != "日常":
                tags.add('-'.join(lazy_pinyin(project, style=Style.TONE3, neutral_tone_with_five=True)))

            # 报销
            if cate_a == "报销款":
                account_income = self.account_reimburse
                links.add('Reimburse')
            elif cate_a == '漏记款':
                account_income = self.account_ufo
            else:
                account_income = self.__get_income(cate_a)

            meta = data.new_metadata(file_name, row)
            meta['time'] = time_value
            txn = data.Transaction(meta, date_value, "*", payer, narration.strip(),
                                   tags, links, [])
            txn.postings.append(
                data.Posting(self.__get_account(account), data.Amount(D(amount), self.__get_currency(currency)), None,
                             None, None, None))

            txn.postings.append(
                data.Posting(account_income, None, None, None,
                             None, None))
            return txn

        return self.__handle_sheet(sheet, handler)

    def __handle_trans(self, sheet, file_name, book_name):
        def handler(read, date_value, time_value, row):
            account_out = read('B')
            amount = read('C')
            currency_out = read('D')
            account_in = read('E')
            currency_in = read('G')
            narration = read('H')

            if narration == '':
                narration = '转账：%s -> %s' % (
                    account_out, account_in)

            # 币种转换

            meta = data.new_metadata(file_name, row)
            meta['time'] = time_value
            txn = data.Transaction(meta, date_value, '*' if currency_in == currency_out else '!', None,
                                   narration,
                                   set(book_name) if book_name is not None else set(), set(), [])
            txn.postings.append(
                data.Posting(self.__get_account(account_in), data.Amount(D(amount), self.__get_currency(currency_out)),
                             None,
                             None, None, None))
            txn.postings.append(
                data.Posting(self.__get_account(account_out), None, None,
                             None, None, None))
            return txn

        return self.__handle_sheet(sheet, handler)
