"""Unit tests for app.core.slugs — no database needed."""

import re

from app.core.slugs import generate_unique_slug, slugify

_SLUG_CHARSET = re.compile(r"^[a-z0-9-]+$")


class TestSlugify:
    def test_basic_name(self):
        assert slugify("Beacon Family Office") == "beacon-family-office"

    def test_strips_symbols_and_collapses_hyphens(self):
        assert slugify("Acme & Co.  --  LLC!") == "acme-co-llc"

    def test_empty_or_symbol_only_falls_back_to_generated_slug(self):
        for value in ["", "   ", "!!!", "🎉🎉🎉"]:
            result = slugify(value)
            assert result
            assert _SLUG_CHARSET.match(result)


class TestGenerateUniqueSlug:
    def test_no_collision_returns_root(self):
        assert generate_unique_slug("Beacon Capital", exists=lambda s: False) == "beacon-capital"

    def test_collision_appends_incrementing_suffix(self):
        taken = {"beacon-capital"}
        assert (
            generate_unique_slug("Beacon Capital", exists=lambda s: s in taken)
            == "beacon-capital-2"
        )

    def test_multiple_collisions_increment_further(self):
        taken = {"beacon-capital", "beacon-capital-2", "beacon-capital-3"}
        assert (
            generate_unique_slug("Beacon Capital", exists=lambda s: s in taken)
            == "beacon-capital-4"
        )

    def test_reserved_word_is_bumped_past_like_a_collision(self):
        assert generate_unique_slug("App", exists=lambda s: False) == "app-2"

    def test_reserved_word_collision_still_increments(self):
        taken = {"app-2"}
        assert (
            generate_unique_slug("App", exists=lambda s: s in taken) == "app-3"
        )
