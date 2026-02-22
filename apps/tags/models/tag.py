from __future__ import annotations

from django.db import models

from core.models import SluggedModel

class Tag(SluggedModel):
    """Taxonomy tag used to categorize competitive programming problems."""

    name = models.CharField(max_length=64, unique=True)
    code = models.SlugField(max_length=64, unique=True)
    problems = models.ManyToManyField("problems.Problem", related_name="tags", blank=True)

    class Meta:
        db_table = "tags_tag"
        ordering = ("name",)
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        indexes = [
            models.Index(fields=["name"], name="tag_name_idx"),
            models.Index(fields=["code"], name="tag_code_idx"),
        ]

    def __str__(self) -> str:
        """Return a readable tag name."""

        return self.name

    def get_slug_source(self) -> str:
        """Return source text used for slug generation."""

        return self.code

    @property
    def problem_count(self) -> int:
        """Return number of problems associated with this tag."""

        return self.problems.count()
