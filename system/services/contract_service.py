from __future__ import annotations

from sqlalchemy.orm import Session

from data.repositories.contract_repo import ContractRepository


class ContractService:
    def __init__(self, db: Session) -> None:
        self.repo = ContractRepository(db)

    def list_internet(self, customer_id: int | None = None):
        return self.repo.list_internet(customer_id)

    def list_hotspot(self, customer_id: int | None = None):
        return self.repo.list_hotspot(customer_id)
