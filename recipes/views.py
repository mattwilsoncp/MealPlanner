import re
import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
)
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Avg, Q
from .models import Recipe
from .forms import RecipeForm, RatingForm, ImportForm, LLMImportForm
from .youtube import YouTubeService, InvalidVideoError, APIError
from .parsing import RecipeParsingService
from ingredients.models import IngredientLink, Ingredient
from instructions.models import Instruction
from tags.models import RecipeTag, Tag
from ratings.models import Rating


UNIT_CHOICES = [
    ("oz", "ounce"),
    ("lb", "pound"),
    ("cup", "cup"),
    ("tbsp", "tablespoon"),
    ("tsp", "teaspoon"),
    ("g", "gram"),
    ("kg", "kilogram"),
    ("ml", "milliliter"),
    ("l", "liter"),
    ("piece", "piece"),
    ("clove", "clove"),
    ("slice", "slice"),
    ("bunch", "bunch"),
    ("can", "can"),
]


class RecipeListView(LoginRequiredMixin, ListView):
    model = Recipe
    template_name = "recipes/recipe_list.html"
    context_object_name = "recipes"

    SORT_CHOICES = [
        ("newest", "Newest First"),
        ("oldest", "Oldest First"),
        ("rating", "Highest Rated"),
        ("title", "Title A-Z"),
    ]


class RecipeImportView(LoginRequiredMixin, FormView):
    form_class = ImportForm
    template_name = "recipes/import.html"
    success_url = reverse_lazy("recipes:recipe_create")

    SORT_CHOICES = [
        ("newest", "Newest First"),
        ("oldest", "Oldest First"),
        ("rating", "Highest Rated"),
        ("title", "Title A-Z"),
    ]

    def form_valid(self, form):
        youtube_url = form.cleaned_data["youtube_url"]

        api_key = getattr(settings, "YOUTUBE_API_KEY", None)
        if not api_key:
            form.add_error(
                "youtube_url", "YouTube API key not configured. Please contact support."
            )
            return self.form_invalid(form)

        try:
            youtube_service = YouTubeService(api_key)
            video_id = youtube_service.extract_video_id(youtube_url)
            metadata = youtube_service.get_video_metadata(video_id)

            parser = RecipeParsingService()

            # Try to get transcript for better content extraction
            full_text = metadata.description
            try:
                transcript = youtube_service.get_transcript(youtube_url)
                if transcript:
                    full_text = transcript
            except Exception:
                pass  # Fall back to description

            ingredients = parser.parse_ingredients(full_text)
            instructions = parser.parse_instructions(full_text)
            unparsed = parser.identify_unparseable(full_text.split("\n"))

            self.request.session["youtube_import"] = {
                "video_id": metadata.video_id,
                "title": metadata.title,
                "description": full_text,
                "thumbnail_url": metadata.thumbnail_url,
                "ingredients": [
                    {
                        "name": i.name,
                        "quantity": i.quantity,
                        "unit": i.unit,
                        "notes": i.notes,
                    }
                    for i in ingredients
                ],
                "instructions": [
                    {
                        "step_number": i.step_number,
                        "text": i.text,
                        "timestamp": i.timestamp,
                    }
                    for i in instructions
                ],
                "unparsed_lines": unparsed,
            }

            messages.success(
                self.request,
                f"Imported: {metadata.title} ({len(ingredients)} ingredients, {len(instructions)} steps)",
            )
            return redirect(self.success_url)

        except InvalidVideoError as e:
            form.add_error("youtube_url", str(e))
            return self.form_invalid(form)
        except APIError as e:
            form.add_error("youtube_url", str(e))
            return self.form_invalid(form)
        except Exception as e:
            form.add_error(
                "youtube_url",
                "Could not fetch video. Please check the URL and try again.",
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{error}")
        return self.render_to_response(self.get_context_data(form=form))

    def get_queryset(self):
        queryset = Recipe.objects.filter(
            household=self.request.user.household, needs_review=False
        )

        search_q = self.request.GET.get("q")
        if search_q:
            queryset = queryset.filter(
                Q(title__icontains=search_q) | Q(description__icontains=search_q)
            )

        sort_by = self.request.GET.get("sort", "newest")
        if sort_by == "newest":
            queryset = queryset.order_by("-created_at")
        elif sort_by == "oldest":
            queryset = queryset.order_by("created_at")
        elif sort_by == "rating":
            queryset = queryset.annotate(avg_rating=Avg("rating__score")).order_by(
                "-avg_rating"
            )
        elif sort_by == "title":
            queryset = queryset.order_by("title")
        else:
            queryset = queryset.order_by("-created_at")

        return queryset.select_related("household").prefetch_related(
            "tags", "rating_set"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["sort"] = self.request.GET.get("sort", "newest")
        context["sort_choices"] = self.SORT_CHOICES
        return context


class LLMRecipeImportView(LoginRequiredMixin, FormView):
    form_class = LLMImportForm
    template_name = "recipes/llm_import.html"
    success_url = reverse_lazy("recipes:recipe_list")

    YouTubeTranscriptApi = None

    UNIT_MAP = {
        "cups": "cup",
        "cup": "cup",
        "tablespoon": "tbsp",
        "tablespoons": "tbsp",
        "tbsp": "tbsp",
        "tbs": "tbsp",
        "teaspoon": "tsp",
        "teaspoons": "tsp",
        "tsp": "tsp",
        "ts": "tsp",
        "ounce": "oz",
        "ounces": "oz",
        "oz": "oz",
        "pound": "lb",
        "pounds": "lb",
        "lb": "lb",
        "gram": "g",
        "grams": "g",
        "g": "g",
        "kilogram": "kg",
        "kilograms": "kg",
        "kg": "kg",
        "milliliter": "ml",
        "milliliters": "ml",
        "ml": "ml",
        "liter": "l",
        "liters": "l",
        "l": "l",
        "cloves": "clove",
        "clove": "clove",
        "slice": "slice",
        "slices": "slice",
        "bunch": "bunch",
        "bunches": "bunch",
        "can": "can",
        "cans": "can",
        "piece": "piece",
        "pieces": "piece",
        "": "piece",
    }

    VALID_UNITS = {"oz", "lb", "cup", "tbsp", "tsp", "g", "kg", "ml", "l", "piece", "clove", "slice", "bunch", "can"}

    PROMPT_TEMPLATE = """You are extracting structured recipe data from a YouTube recipe video transcript.
Return only valid JSON with this exact shape:
{{
  "title": "string",
  "description": "string",
  "ingredients": [
    {{
      "name": "string",
      "quantity": "string",
      "unit": "string"
    }}
  ],
  "instructions": [
    {{
      "step_number": 1,
      "text": "string"
    }}
  ]
}}

Rules:
- The recipe title should be concise and human readable.
- The description should summarize the dish in 1-3 sentences.
- Include only actual ingredients used in the recipe.
- Preserve ingredient quantities when present.
- Use singular common cooking units when possible.
- For ingredients without a clear quantity, leave quantity as an empty string.
- For ingredients without a clear unit, leave unit as an empty string.
- Instructions should be clean, imperative cooking steps.
- Instructions must be ordered and start at step_number 1.
- Do not include markdown, explanation, or code fences.
- Use all provided source context, including title, description, and transcript, but prioritize explicit recipe details from the transcript when they conflict with metadata.

Source Context:
{source_context}
"""

    def form_valid(self, form):
        import os
        import json
        import re
        from decimal import Decimal, InvalidOperation
        from pathlib import Path
        from datetime import datetime
        import urllib.request

        from django.conf import settings
        from openai import OpenAI

        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            LLMRecipeImportView.YouTubeTranscriptApi = YouTubeTranscriptApi
        except ImportError:
            LLMRecipeImportView.YouTubeTranscriptApi = None

        from household.models import Household
        from ingredients.models import Ingredient, IngredientLink
        from instructions.models import Instruction
        from .models import Recipe
        from .youtube import YouTubeService, InvalidVideoError

        PROJECT_ROOT = Path(__file__).resolve().parent.parent
        youtube_url = form.cleaned_data["youtube_url"]
        model = form.cleaned_data.get("model") or "qwen/qwen-turbo"

        OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not OPENROUTER_API_KEY:
            form.add_error(
                "youtube_url",
                "OPENROUTER_API_KEY is not configured. Please set it in your environment.",
            )
            return self.form_invalid(form)

        try:
            household = self.request.user.household
            if not household:
                form.add_error(
                    "youtube_url", "No household associated with your account."
                )
                return self.form_invalid(form)

            client = OpenAI(
                api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1"
            )

            video_id = self._extract_video_id(youtube_url)
            metadata = self._get_video_metadata(video_id, youtube_url)
            transcript = self._fetch_transcript(video_id)
            transcript_log = self._write_transcript_log(metadata, transcript)
            parsed = self._parse_with_llm(client, model, metadata, transcript)

            if form.cleaned_data.get("title"):
                parsed["title"] = form.cleaned_data["title"]

            recipe = self._create_recipe(parsed, household, youtube_url, transcript_log, video_id)

            messages.success(
                self.request,
                f"Imported recipe: {recipe.title} ({len(parsed.get('ingredients', []))} ingredients, {len(parsed.get('instructions', []))} steps)",
            )
            return redirect("recipes:recipe_detail", pk=recipe.pk)

        except InvalidVideoError as e:
            form.add_error("youtube_url", str(e))
            return self.form_invalid(form)
        except Exception as e:
            form.add_error("youtube_url", f"Import failed: {str(e)}")
            return self.form_invalid(form)

    def _extract_video_id(self, url: str) -> str:
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise InvalidVideoError("Invalid YouTube URL")

    def _get_video_metadata(self, video_id: str, youtube_url: str) -> dict:
        api_key = getattr(settings, "YOUTUBE_API_KEY", None)
        metadata = {
            "video_id": video_id,
            "url": youtube_url,
            "title": "",
            "description": "",
            "thumbnail_url": "",
            "metadata_status": "not_requested",
            "metadata_error": "",
        }

        if not api_key:
            metadata["metadata_status"] = "missing_api_key"
            metadata["metadata_error"] = (
                "YOUTUBE_API_KEY was not found in the environment or Django settings"
            )
            return metadata

        try:
            service = YouTubeService(api_key=api_key)
            video_metadata = service.get_video_metadata(video_id)
        except Exception as exc:
            metadata["metadata_status"] = "error"
            metadata["metadata_error"] = str(exc)
            return metadata

        metadata["title"] = video_metadata.title or ""
        metadata["description"] = video_metadata.description or ""
        metadata["thumbnail_url"] = video_metadata.thumbnail_url or ""
        metadata["metadata_status"] = "ok"
        return metadata

    def _fetch_transcript(self, video_id: str) -> str:
        if LLMRecipeImportView.YouTubeTranscriptApi is not None:
            errors = []
            transcript_items = None

            try:
                transcript_items = LLMRecipeImportView.YouTubeTranscriptApi.get_transcript(
                    video_id, languages=["en", "en-US", "en-GB"]
                )
            except Exception as exc:
                errors.append(f"get_transcript failed: {exc}")

            if transcript_items is None:
                try:
                    api = LLMRecipeImportView.YouTubeTranscriptApi()
                    transcript_items = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
                except TypeError:
                    try:
                        transcript_items = api.fetch(video_id)
                    except Exception as exc:
                        errors.append(f"fetch failed: {exc}")
                except Exception as exc:
                    errors.append(f"fetch failed: {exc}")

            if transcript_items is None:
                try:
                    api = LLMRecipeImportView.YouTubeTranscriptApi()
                    transcript_list = api.list(video_id)
                    preferred_languages = ["en", "en-US", "en-GB"]
                    selected_transcript = None
                    for language_code in preferred_languages:
                        try:
                            selected_transcript = transcript_list.find_transcript(
                                [language_code]
                            )
                            break
                        except Exception:
                            continue
                    if selected_transcript is None:
                        try:
                            selected_transcript = transcript_list.find_generated_transcript(
                                preferred_languages
                            )
                        except Exception:
                            selected_transcript = None
                    if selected_transcript is not None:
                        transcript_items = selected_transcript.fetch()
                except Exception as exc:
                    errors.append(f"list/fetch transcript track failed: {exc}")

            lines = []
            if transcript_items is not None:
                for item in transcript_items:
                    if isinstance(item, dict):
                        text = str(item.get("text") or "").strip()
                    else:
                        text = str(getattr(item, "text", "") or "").strip()
                    if text:
                        lines.append(text)

            transcript_text = "\n".join(lines).strip()
            if transcript_text:
                return transcript_text

            error_message = "; ".join(errors) if errors else "No transcript text returned"
            raise RuntimeError(f"Could not fetch YouTube captions: {error_message}")

        raise RuntimeError("youtube-transcript-api is not installed")

    def _write_transcript_log(self, metadata: dict, transcript: str) -> Path:
        from pathlib import Path
        TRANSCRIPT_DIR = Path(__file__).resolve().parent.parent / "logs" / "transcripts"
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_video_id = metadata.get("video_id") or "unknown_video"
        output_path = TRANSCRIPT_DIR / f"{timestamp}_{safe_video_id}.txt"
        log_body = (
            f"Source URL: {metadata.get('url', '')}\n"
            f"Video ID: {metadata.get('video_id', '')}\n"
            f"Metadata Status: {metadata.get('metadata_status', '')}\n"
            f"Metadata Error: {metadata.get('metadata_error', '')}\n"
            f"Title: {metadata.get('title', '')}\n"
            f"Thumbnail URL: {metadata.get('thumbnail_url', '')}\n"
            "\n"
            "Description:\n"
            f"{metadata.get('description', '')}\n"
            "\n"
            "Full Transcript:\n"
            f"{transcript}\n"
        )
        output_path.write_text(log_body, encoding="utf-8")
        return output_path

    def _parse_with_llm(
        self, client: OpenAI, model: str, metadata: dict, transcript: str
    ) -> dict:
        if not transcript:
            raise RuntimeError("No transcript available for this video")

        prompt = self.PROMPT_TEMPLATE.format(
            source_context=self._build_source_context(metadata, transcript)
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise recipe extraction engine that returns strict JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=4000,
        )

        content = response.choices[0].message.content or ""
        if not content.strip():
            raise RuntimeError("OpenRouter returned an empty response")

        return self._extract_json_payload(content)

    def _build_source_context(self, metadata: dict, transcript: str) -> str:
        return (
            f"Source URL: {metadata.get('url', '')}\n"
            f"Video ID: {metadata.get('video_id', '')}\n"
            f"Title: {metadata.get('title', '')}\n"
            f"Thumbnail URL: {metadata.get('thumbnail_url', '')}\n"
            "\n"
            "Description:\n"
            f"{metadata.get('description', '')}\n"
            "\n"
            "Full Transcript:\n"
            f"{transcript}"
        )

    def _extract_json_payload(self, raw_text: str) -> dict:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise RuntimeError("Model response was not a JSON object")
        return payload

    def _normalize_quantity(self, raw_quantity: any) -> Decimal:
        if raw_quantity is None:
            return Decimal("1")

        quantity_text = str(raw_quantity).strip()
        if not quantity_text:
            return Decimal("1")

        fraction_match = re.fullmatch(r"(\d+)\s*/\s*(\d+)", quantity_text)
        mixed_match = re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", quantity_text)
        range_match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", quantity_text
        )

        try:
            if mixed_match:
                whole = Decimal(mixed_match.group(1))
                numerator = Decimal(mixed_match.group(2))
                denominator = Decimal(mixed_match.group(3))
                return whole + (numerator / denominator)
            if fraction_match:
                numerator = Decimal(fraction_match.group(1))
                denominator = Decimal(fraction_match.group(2))
                return numerator / denominator
            if range_match:
                low = Decimal(range_match.group(1))
                high = Decimal(range_match.group(2))
                return (low + high) / 2
            return Decimal(quantity_text)
        except (InvalidOperation, ZeroDivisionError):
            return Decimal("1")

    def _normalize_unit(self, raw_unit: any) -> str:
        unit = str(raw_unit or "").strip().lower()
        normalized = self.UNIT_MAP.get(unit, unit)
        if normalized in self.VALID_UNITS:
            return normalized
        return "piece"

    def _create_recipe(
        self, data: dict, household, youtube_url: str, transcript_log: Path, video_id: str = None
    ) -> Recipe:
        from django.core.files import File
        from pathlib import Path

        PROJECT_ROOT = Path(__file__).resolve().parent.parent

        title = str(data.get("title") or "").strip() or "Imported YouTube Recipe"
        description = str(data.get("description") or "").strip()
        ingredients = data.get("ingredients") or []
        instructions = data.get("instructions") or []

        recipe, created = Recipe.objects.get_or_create(
            household=household,
            title=title,
            defaults={
                "description": description,
                "video_url": youtube_url,
                "needs_review": True,
            },
        )

        recipe.description = description or recipe.description
        recipe.video_url = youtube_url
        recipe.needs_review = True

        if video_id and not recipe.photo:
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            media_root = settings.MEDIA_ROOT
            recipe_photos_dir = media_root / "recipe_photos"
            recipe_photos_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{household.id}_{video_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            output_path = recipe_photos_dir / filename

            try:
                urllib.request.urlretrieve(thumbnail_url, output_path)
                with open(output_path, "rb") as f:
                    recipe.photo.save(filename, File(f), save=True)
            except Exception:
                fallback_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                try:
                    urllib.request.urlretrieve(fallback_url, output_path)
                    with open(output_path, "rb") as f:
                        recipe.photo.save(filename, File(f), save=True)
                except Exception:
                    pass

        recipe.save()

        recipe.ingredients.all().delete()
        Instruction.objects.filter(recipe=recipe).delete()

        for index, item in enumerate(ingredients, start=1):
            name = str(item.get("name") or "").strip()
            if not name:
                continue

            ingredient, _ = Ingredient.objects.get_or_create(
                household=household,
                name=name,
            )
            IngredientLink.objects.create(
                recipe=recipe,
                ingredient=ingredient,
                quantity=self._normalize_quantity(item.get("quantity")),
                unit=self._normalize_unit(item.get("unit")),
                order=index,
            )

        for index, item in enumerate(instructions, start=1):
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            step_number = item.get("step_number")
            if not isinstance(step_number, int) or step_number < 1:
                step_number = index
            Instruction.objects.create(
                recipe=recipe,
                step_number=step_number,
                text=text,
            )

        recipe.description = (recipe.description or "").strip()
        if str(transcript_log) not in recipe.description:
            suffix = f"\n\nTranscript log: {transcript_log.relative_to(PROJECT_ROOT)}"
            recipe.description = f"{recipe.description}{suffix}".strip()
            recipe.save(update_fields=["description", "updated_at"])

        return recipe


class RecipeDetailView(LoginRequiredMixin, DetailView):
    model = Recipe
    template_name = "recipes/recipe_detail.html"

    def get_queryset(self):
        household = self.request.user.household
        if household:
            return Recipe.objects.filter(household=household) | Recipe.objects.filter(
                needs_review=True
            )
        return Recipe.objects.filter(needs_review=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recipe = self.object

        context["ingredients"] = (
            IngredientLink.objects.filter(
                recipe=recipe,
                ingredient__household=self.request.user.household,
            )
            .select_related("ingredient", "inventory_item")
            .order_by("order")
        )

        context["instructions"] = Instruction.objects.filter(recipe=recipe).order_by(
            "step_number"
        )

        context["tags"] = RecipeTag.objects.filter(recipe=recipe).select_related("tag")

        context["ratings"] = Rating.objects.filter(recipe=recipe)

        if context["ratings"].exists():
            avg = context["ratings"].values_list("score", flat=True)
            context["average_rating"] = sum(avg) / len(avg)
        else:
            context["average_rating"] = None

        existing_rating = Rating.objects.filter(
            recipe=recipe, user=self.request.user
        ).first()
        if existing_rating:
            context["rating_form"] = RatingForm(instance=existing_rating)
        else:
            context["rating_form"] = RatingForm()

        return context


class RecipeCreateView(LoginRequiredMixin, CreateView):
    model = Recipe
    form_class = RecipeForm
    template_name = "recipes/recipe_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unit_choices"] = UNIT_CHOICES

        youtube_import = self.request.session.get("youtube_import")
        if youtube_import:
            context["youtube_import"] = youtube_import
            context["has_youtube_import"] = True
            context["youtube_ingredients"] = youtube_import.get("ingredients", [])
            context["youtube_instructions"] = youtube_import.get("instructions", [])
            context["youtube_unparsed"] = youtube_import.get("unparsed_lines", [])

        return context

    def get_initial(self):
        initial = super().get_initial()
        youtube_import = self.request.session.get("youtube_import")
        if youtube_import:
            initial["title"] = youtube_import.get("title", "")
            initial["description"] = youtube_import.get("description", "")
        return initial

    def form_valid(self, form):
        youtube_import = self.request.session.get("youtube_import")

        form.instance.household = self.request.user.household
        recipe = form.save(commit=False)
        recipe.save()

        if youtube_import:
            ingredients = youtube_import.get("ingredients", [])
            for ing in ingredients:
                name = ing.get("name", "").strip()
                if name:
                    quantity = float(ing.get("quantity", 1)) or 1
                    unit = ing.get("unit", "piece") or "piece"

                    ing_obj, _ = Ingredient.objects.get_or_create(
                        household=recipe.household,
                        name__iexact=name,
                        defaults={"household": recipe.household, "name": name},
                    )
                    IngredientLink.objects.create(
                        recipe=recipe,
                        ingredient=ing_obj,
                        quantity=quantity,
                        unit=unit,
                    )

            instructions = youtube_import.get("instructions", [])
            for inst in instructions:
                text = inst.get("text", "").strip()
                if text:
                    step = inst.get("step_number", 1)
                    Instruction.objects.create(
                        recipe=recipe,
                        step_number=step,
                        text=text,
                    )

            del self.request.session["youtube_import"]
            messages.success(
                self.request, f"Recipe '{recipe.title}' created from YouTube import!"
            )
        else:
            self._save_ingredients(recipe)
            self._save_instructions(recipe)
            messages.success(self.request, f"Recipe '{recipe.title}' created!")

        return redirect("recipes:recipe_detail", pk=recipe.pk)

    def _save_ingredients(self, recipe):
        names = self.request.POST.getlist("ingredient_name")
        quantities = self.request.POST.getlist("ingredient_quantity")
        units = self.request.POST.getlist("ingredient_unit")

        for i, name in enumerate(names):
            name = name.strip()
            if name:
                quantity = (
                    float(quantities[i]) if i < len(quantities) and quantities[i] else 1
                )
                unit = units[i] if i < len(units) and units[i] else "piece"

                ing, _ = Ingredient.objects.get_or_create(
                    household=recipe.household,
                    name__iexact=name,
                    defaults={"household": recipe.household, "name": name},
                )
                IngredientLink.objects.create(
                    recipe=recipe,
                    ingredient=ing,
                    quantity=quantity,
                    unit=unit,
                )

    def _save_instructions(self, recipe):
        texts = self.request.POST.getlist("instruction_text")
        orders = self.request.POST.getlist("instruction_step")

        for i, text in enumerate(texts):
            text = text.strip()
            if text:
                order = int(orders[i]) if i < len(orders) and orders[i] else i + 1
                Instruction.objects.create(
                    recipe=recipe,
                    step_number=order,
                    text=text,
                )


class RecipeUpdateView(LoginRequiredMixin, UpdateView):
    model = Recipe
    form_class = RecipeForm
    template_name = "recipes/recipe_form.html"

    def get_queryset(self):
        return Recipe.objects.filter(household=self.request.user.household)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unit_choices"] = UNIT_CHOICES
        recipe = self.object

        context["ingredients"] = IngredientLink.objects.filter(
            recipe=recipe
        ).select_related("ingredient")
        context["instructions"] = Instruction.objects.filter(recipe=recipe).order_by(
            "step_number"
        )
        context["tags"] = RecipeTag.objects.filter(recipe=recipe).select_related("tag")
        context["available_tags"] = Tag.objects.filter(
            household=self.request.user.household
        )

        return context

    def form_valid(self, form):
        recipe = form.save(commit=False)
        recipe.save()

        IngredientLink.objects.filter(recipe=recipe).delete()
        self._save_ingredients(recipe)

        Instruction.objects.filter(recipe=recipe).delete()
        self._save_instructions(recipe)

        return redirect("recipes:recipe_detail", pk=recipe.pk)

    def _save_ingredients(self, recipe):
        names = self.request.POST.getlist("ingredient_name")
        quantities = self.request.POST.getlist("ingredient_quantity")
        units = self.request.POST.getlist("ingredient_unit")

        for i, name in enumerate(names):
            name = name.strip()
            if name:
                quantity = (
                    float(quantities[i]) if i < len(quantities) and quantities[i] else 1
                )
                unit = units[i] if i < len(units) and units[i] else "piece"

                ing, _ = Ingredient.objects.get_or_create(
                    household=recipe.household,
                    name__iexact=name,
                    defaults={"household": recipe.household, "name": name},
                )
                IngredientLink.objects.create(
                    recipe=recipe,
                    ingredient=ing,
                    quantity=quantity,
                    unit=unit,
                )

    def _save_instructions(self, recipe):
        texts = self.request.POST.getlist("instruction_text")
        orders = self.request.POST.getlist("instruction_step")

        for i, text in enumerate(texts):
            text = text.strip()
            if text:
                order = int(orders[i]) if i < len(orders) and orders[i] else i + 1
                Instruction.objects.create(
                    recipe=recipe,
                    step_number=order,
                    text=text,
                )


class RecipeDeleteView(LoginRequiredMixin, DeleteView):
    model = Recipe
    template_name = "recipes/recipe_confirm_delete.html"
    success_url = reverse_lazy("recipes:recipe_list")

    def get_queryset(self):
        return Recipe.objects.filter(household=self.request.user.household)


@require_POST
def recipe_rate_view(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, household=request.user.household)

    existing_rating = Rating.objects.filter(recipe=recipe, user=request.user).first()

    if existing_rating:
        form = RatingForm(request.POST, instance=existing_rating)
    else:
        form = RatingForm(request.POST)

    if form.is_valid():
        rating = form.save(commit=False)
        rating.recipe = recipe
        rating.user = request.user
        rating.save()
        messages.success(request, "Rating saved!")

    return redirect("recipes:recipe_detail", pk=pk)
