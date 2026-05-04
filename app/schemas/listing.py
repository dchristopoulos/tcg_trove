from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ListingCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    price: int = Field(gt=0)
    location: str = Field(min_length=2, max_length=120)
    size: int = Field(gt=0)
    bedrooms: int = Field(ge=0, le=2100)
    bathrooms: int = Field(ge=1, le=30)
    property_type: str = Field(min_length=3, max_length=40)
    furnished: str = Field(
        pattern=r"^(near_mint|lightly_played|moderately_played|heavily_played|damaged|furnished|semi_furnished|unfurnished)$"
    )
    description: str = Field(min_length=30, max_length=2000)
    seller_id: int
    image_url: str = Field(min_length=3, max_length=400)


class ListingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: int
    location: str
    size: int
    bedrooms: int
    bathrooms: int
    property_type: str
    furnished: str
    description: str
    image_url: str
    seller_id: int


class ListingPriceHistoryRead(BaseModel):
    price: int
    changed_at: datetime


class ListingPageRead(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ListingRead]


class ListingSummaryRead(BaseModel):
    total: int
    min_price: int | None
    max_price: int | None
    avg_price: float | None
    avg_size: float | None


class MarketPulseBucketRead(BaseModel):
    label: str
    count: int


class MarketPulseLocationRead(BaseModel):
    location: str
    count: int


class ListingMarketPulseRead(BaseModel):
    total_listings: int
    avg_price: float | None
    avg_size: float | None
    top_locations: list[MarketPulseLocationRead]
    price_buckets: list[MarketPulseBucketRead]


class ListingCompareItemRead(BaseModel):
    listing: ListingRead
    price_per_size: float


class ListingCompareRead(BaseModel):
    items: list[ListingCompareItemRead]
    cheapest_listing_id: int | None
    largest_listing_id: int | None
    best_value_listing_id: int | None


class ListingRecommendationItemRead(BaseModel):
    listing: ListingRead
    score: float
    reasons: list[str]


class ListingRecommendationsRead(BaseModel):
    user_id: int
    items: list[ListingRecommendationItemRead]


class ListingFilter(BaseModel):
    min_price: int | None = None
    max_price: int | None = None
    min_size: int | None = None
    max_size: int | None = None
    min_bedrooms: int | None = None
    max_bedrooms: int | None = None
    min_bathrooms: int | None = None
    max_bathrooms: int | None = None
    property_type: str | None = None
    furnished: str | None = None
    location: str | None = None
    query: str | None = None
    sort_by: str | None = None
    sort_order: str | None = None

    @field_validator("property_type", "furnished", "location", "query", "sort_by", "sort_order", mode="before")
    @classmethod
    def normalize_blank_strings(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price cannot be greater than max_price")
        if self.min_size is not None and self.max_size is not None and self.min_size > self.max_size:
            raise ValueError("min_size cannot be greater than max_size")
        if self.min_bedrooms is not None and self.max_bedrooms is not None and self.min_bedrooms > self.max_bedrooms:
            raise ValueError("min_bedrooms cannot be greater than max_bedrooms")
        if self.min_bathrooms is not None and self.max_bathrooms is not None and self.min_bathrooms > self.max_bathrooms:
            raise ValueError("min_bathrooms cannot be greater than max_bathrooms")
        if self.furnished is not None and self.furnished not in {
            "near_mint",
            "lightly_played",
            "moderately_played",
            "heavily_played",
            "damaged",
            "furnished",
            "semi_furnished",
            "unfurnished",
        }:
            raise ValueError("condition must be a valid card condition")
        if self.sort_by is not None and self.sort_by not in {"price", "size", "bedrooms", "bathrooms", "created", "title"}:
            raise ValueError("sort_by must be one of price, stock, year, rarity score, created, title")
        if self.sort_order is not None and self.sort_order not in {"asc", "desc"}:
            raise ValueError("sort_order must be asc or desc")
        return self

