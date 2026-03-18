from pydantic import BaseModel

from ..repr_html import to_html_with_styles


class Object(BaseModel):
    def _repr_html_(self):
        return to_html_with_styles(self)
