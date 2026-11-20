class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(255), nullable=False)
    billing_type = Column(String(50), nullable=False)          -- "aylık" or "tek seferlik"
    speed_or_capacity_option = Column(String(255))               -- e.g., "100 Mbps ME Internet Hizmeti"
    table_reference = Column(String(50))                         -- e.g., "Tablo-1", "Tablo-2"