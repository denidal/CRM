from sqlalchemy.orm import Session
from data.models.product import Product

def get_product_by_id(db: Session, product_id: int):
    return db.query(Product).filter(Product.product_id == product_id).first()

def create_product(db: Session, product_name: str, billing_type: str, speed_option: str, table_ref: str):
    db_product = Product(
        product_name=product_name,
        billing_type=billing_type,
        speed_or_capacity_option=speed_option,
        table_reference=table_ref
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product