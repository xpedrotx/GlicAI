"""Supabase falso em memória, só o suficiente pra testar a lógica dos services sem rede."""
import re
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace


class FakeQuery:
    def __init__(self, store, table_name):
        self.store = store
        self.table_name = table_name
        self.filters = []
        self.op = None
        self.payload = None
        self.order_col = None
        self.order_desc = False
        self.limit_n = None

    def select(self, *_args, **_kwargs):
        self.op = "select"
        return self

    def insert(self, payload):
        self.op = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.op = "update"
        self.payload = payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def gte(self, col, val):
        self.filters.append(("gte", col, val))
        return self

    def lte(self, col, val):
        self.filters.append(("lte", col, val))
        return self

    def is_(self, col, val):
        self.filters.append(("is", col, val))
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, vals))
        return self

    def like(self, col, pattern):
        self.filters.append(("like", col, pattern))
        return self

    def neq(self, col, val):
        self.filters.append(("neq", col, val))
        return self

    def order(self, col, desc=False):
        self.order_col = col
        self.order_desc = desc
        return self

    def limit(self, n):
        self.limit_n = n
        return self

    def _match(self, row):
        for kind, col, val in self.filters:
            if kind == "eq" and row.get(col) != val:
                return False
            if kind == "gte" and (row.get(col) is None or row.get(col) < val):
                return False
            if kind == "lte" and (row.get(col) is None or row.get(col) > val):
                return False
            if kind == "is":
                eh_null = row.get(col) is None
                if val == "null" and not eh_null:
                    return False
                if val != "null" and eh_null:
                    return False
            if kind == "in" and row.get(col) not in val:
                return False
            if kind == "like":
                valor = row.get(col)
                if valor is None:
                    return False
                # só precisamos de padrões simples tipo "prefixo@%" — troca
                # "%" (curinga do SQL LIKE) por ".*" e ancora a regex
                padrao = "^" + re.escape(val).replace("%", ".*") + "$"
                if not re.match(padrao, valor):
                    return False
            if kind == "neq" and row.get(col) == val:
                return False
        return True

    def execute(self):
        table = self.store.setdefault(self.table_name, [])
        if self.op == "insert":
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            results = []
            for row in rows:
                row = dict(row)
                row.setdefault("id", str(uuid.uuid4()))
                now = datetime.now(timezone.utc).isoformat()
                row.setdefault("created_at", now)
                row.setdefault("updated_at", now)
                if self.table_name == "confirmacoes_glicemia":
                    row.setdefault("horario", now)
                    row.setdefault("confirmado_em", None)
                    row.setdefault("lembrete_enviado", False)
                    row.setdefault("lembrete2_enviado", False)
                    row.setdefault("cuidadores_notificados", False)
                if self.table_name in ("cuidadores", "basal", "modificadores_bolus", "lembretes"):
                    row.setdefault("ativo", True)
                if self.table_name == "lembretes":
                    row.setdefault("dias_semana", [0, 1, 2, 3, 4, 5, 6])
                if self.table_name == "convites_cuidador":
                    row.setdefault("usado_em", None)
                if self.table_name in ("registros_glicemia", "registros_bolus"):
                    row.setdefault("horario", now)
                if self.table_name == "registros_bolus":
                    row.setdefault("dose_aplicada", None)
                if self.table_name == "alertas_enviados":
                    row.setdefault("horario_envio", now)
                table.append(row)
                results.append(row)
            return SimpleNamespace(data=results)

        if self.op == "update":
            matched = [r for r in table if self._match(r)]
            for r in matched:
                r.update(self.payload)
            return SimpleNamespace(data=matched)

        if self.op == "delete":
            matched = [r for r in table if self._match(r)]
            self.store[self.table_name] = [r for r in table if not self._match(r)]
            return SimpleNamespace(data=matched)

        rows = [r for r in table if self._match(r)]
        if self.order_col:
            rows = sorted(rows, key=lambda r: r[self.order_col], reverse=self.order_desc)
        if self.limit_n:
            rows = rows[: self.limit_n]
        return SimpleNamespace(data=rows)


class FakeRPC:
    """Fake mínimo pra chamadas supabase.rpc(nome).execute() — usado por
    serviços que chamam funções do Postgres em vez de tabelas."""

    def __init__(self, retorno):
        self._retorno = retorno

    def execute(self):
        return SimpleNamespace(data=self._retorno)


class FakeSupabase:
    def __init__(self):
        self.store = {}
        # nome_da_funcao -> valor que .execute().data deve retornar
        self.rpc_retornos = {}

    def table(self, name):
        return FakeQuery(self.store, name)

    def rpc(self, name, params=None):
        return FakeRPC(self.rpc_retornos.get(name))
