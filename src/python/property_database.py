# ============================================================================
# property_database.py - Banco de Dados de Propriedades Imobiliárias
# ============================================================================
# Gerencia o banco de dados SQLite com 100 propriedades fictícias.
# Fornece ferramenta de busca que a IA pode chamar durante processamento.
# Usa SQLAlchemy como ORM assíncrono.
# ============================================================================

import json
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ========== MODELOS DE DADOS ==========


class Base(DeclarativeBase):
    """Classe base para todos os modelos SQLAlchemy"""

    pass


class Property(Base):
    """
    Modelo de uma propriedade imobiliária.
    Mapeado para tabela 'properties' no SQLite.
    """

    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String)  # Ex: "Detached", "Condo"
    status: Mapped[str] = mapped_column(String)  # Ex: "For Sale", "Sold"
    price: Mapped[int] = mapped_column(Integer)  # Preço em centavos
    currency: Mapped[str] = mapped_column(String)  # Ex: "CAD", "USD"

    # Endereço (armazenado como JSON)
    address_street: Mapped[str] = mapped_column(String)
    address_city: Mapped[str] = mapped_column(String)
    address_province: Mapped[str] = mapped_column(String)
    address_postal_code: Mapped[str] = mapped_column(String)
    address_country: Mapped[str] = mapped_column(String)

    bedrooms: Mapped[int] = mapped_column(Integer)  # Número de quartos
    bathrooms: Mapped[int] = mapped_column(Integer)  # Número de banheiros
    square_footage: Mapped[int] = mapped_column(Integer)  # Área interna em pés quadrados
    lot_size_square_footage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_built: Mapped[int] = mapped_column(Integer)  # Ano de construção
    parking_spaces: Mapped[int] = mapped_column(Integer)  # Vagas de estacionamento

    short_description: Mapped[str] = mapped_column(String)
    full_description: Mapped[str] = mapped_column(String)
    key_features: Mapped[str] = mapped_column(JSON)  # Lista armazenada como JSON
    listed_date: Mapped[str] = mapped_column(String)

    def to_dict(self) -> dict[str, Any]:
        """Converte o modelo para dicionário (para serialização JSON)"""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "price": self.price,
            "currency": self.currency,
            "address": {
                "street": self.address_street,
                "city": self.address_city,
                "province": self.address_province,
                "postalCode": self.address_postal_code,
                "country": self.address_country,
            },
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "squareFootage": self.square_footage,
            "lotSizeSquareFootage": self.lot_size_square_footage,
            "yearBuilt": self.year_built,
            "parkingSpaces": self.parking_spaces,
            "shortDescription": self.short_description,
            "fullDescription": self.full_description,
            "keyFeatures": json.loads(self.key_features)
            if isinstance(self.key_features, str)
            else self.key_features,
            "listedDate": self.listed_date,
        }


# ========== SERVIÇO DE BANCO DE DADOS ==========


class PropertyDatabase:
    """
    Serviço principal do banco de dados.
    Fornece ferramenta de busca que a IA pode chamar.
    """

    def __init__(self, db_path: str = "properties.db"):
        """
        Inicializa o banco de dados com SQLite assíncrono.

        Args:
            db_path: Caminho para o arquivo SQLite
        """
        # Cria engine assíncrono do SQLAlchemy
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def initialize(self):
        """Cria as tabelas no banco de dados"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def seed_data(self, data_dir: str = None):
        """
        Inicializa o banco de dados com dados de exemplo.
        Carrega arquivos JSON de Data/Properties/*.json

        Args:
            data_dir: Diretório contendo os arquivos JSON (opcional)
        """
        # Usar path relativo local por padrão
        if data_dir is None:
            current_file = Path(__file__).resolve()
            data_dir = current_file.parent / "Data" / "Properties"
        else:
            data_dir = Path(data_dir)

        async with self.async_session() as session:
            # Verifica se já existe dados
            result = await session.execute(select(Property).limit(1))
            if result.scalar_one_or_none():
                print("Database already seeded")
                return

            # Carrega todos os arquivos JSON se diretório existir
            if not data_dir.exists():
                print(f"⚠️  Data directory not found: {data_dir}")
                print("📝 Database initialized without sample data.")
                print(
                    "   You can add properties via the API or create Data/Properties/*.json files"
                )
                return

            properties = []
            for json_file in sorted(data_dir.glob("*.json")):
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                    # Converte de camelCase (JSON) para snake_case (Python)
                    property_obj = Property(
                        id=data["id"],
                        type=data["type"],
                        status=data["status"],
                        price=data["price"],
                        currency=data["currency"],
                        address_street=data["address"]["street"],
                        address_city=data["address"]["city"],
                        address_province=data["address"]["province"],
                        address_postal_code=data["address"]["postalCode"],
                        address_country=data["address"]["country"],
                        bedrooms=data["bedrooms"],
                        bathrooms=data["bathrooms"],
                        square_footage=data["squareFootage"],
                        lot_size_square_footage=data.get("lotSizeSquareFootage"),
                        year_built=data["yearBuilt"],
                        parking_spaces=data["parkingSpaces"],
                        short_description=data["shortDescription"],
                        full_description=data["fullDescription"],
                        key_features=json.dumps(data["keyFeatures"]),
                        listed_date=data["listedDate"],
                    )
                    properties.append(property_obj)

            # Insere todas as propriedades
            session.add_all(properties)
            await session.commit()
            print(f"Seeded {len(properties)} properties")

    async def search(
        self,
        city: str | None = None,
        min_bedrooms: int | None = None,
        max_bedrooms: int | None = None,
        min_bathrooms: int | None = None,
        max_bathrooms: int | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        property_type: str | None = None,
        min_square_footage: int | None = None,
        max_square_footage: int | None = None,
        min_parking: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Ferramenta de busca de propriedades que a IA pode chamar.
        Retorna lista de propriedades que correspondem aos critérios.

        Esta é a ferramenta principal que o agente de IA usa durante a fase de busca.
        """
        async with self.async_session() as session:
            query = select(Property)

            # Aplica filtros dinamicamente
            if city:
                query = query.where(Property.address_city.ilike(f"%{city}%"))
            if min_bedrooms is not None:
                query = query.where(Property.bedrooms >= min_bedrooms)
            if max_bedrooms is not None:
                query = query.where(Property.bedrooms <= max_bedrooms)
            if min_bathrooms is not None:
                query = query.where(Property.bathrooms >= min_bathrooms)
            if max_bathrooms is not None:
                query = query.where(Property.bathrooms <= max_bathrooms)
            if min_price is not None:
                query = query.where(Property.price >= min_price)
            if max_price is not None:
                query = query.where(Property.price <= max_price)
            if property_type:
                query = query.where(Property.type.ilike(f"%{property_type}%"))
            if min_square_footage is not None:
                query = query.where(Property.square_footage >= min_square_footage)
            if max_square_footage is not None:
                query = query.where(Property.square_footage <= max_square_footage)
            if min_parking is not None:
                query = query.where(Property.parking_spaces >= min_parking)

            # Limita a 50 resultados
            query = query.limit(50)

            result = await session.execute(query)
            properties = result.scalars().all()

            return [prop.to_dict() for prop in properties]
