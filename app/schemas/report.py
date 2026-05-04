from pydantic import BaseModel


class TopSearchRead(BaseModel):
    query: str
    count: int


class MonthlySupervisorReportRead(BaseModel):
    inquiries_count: int
    saved_properties_count: int
    top_searches: list[TopSearchRead]
