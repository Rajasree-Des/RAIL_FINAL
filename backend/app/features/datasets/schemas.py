from pydantic import BaseModel, ConfigDict, Field


class ColumnMetadata(BaseModel):
    id: str
    field_name: str = Field(alias="fieldName")
    display_name: str = Field(alias="displayName")
    data_type: str = Field(alias="dataType")
    filterable: bool = True
    sortable: bool = True

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)


class DatasetMetadataResponse(BaseModel):
    report_id: str = Field(alias="reportId")
    source_filename: str = Field(alias="sourceFilename")
    header_row: int = Field(alias="headerRow")
    row_count: int = Field(alias="rowCount")
    columns: list[ColumnMetadata]
    parsed_at: str = Field(alias="parsedAt")

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)


class IngestDatasetRequest(BaseModel):
    upload_id: str = Field(alias="uploadId")
    header_row: int = Field(default=1, alias="headerRow")
    sheet_name: str | None = Field(default=None, alias="sheetName")

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)
