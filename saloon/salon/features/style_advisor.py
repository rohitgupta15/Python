import base64
import json
import os
import logging
from uuid import uuid4
from urllib import error, request as urlrequest

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static

from ..forms import StyleConsultationForm
from ..models import Salon, StyleConsultation, Worker

logger = logging.getLogger(__name__)
PAGE_SIZE = 10


def _worker_for_user(user):
    return (
        Worker.objects.select_related("salon")
        .filter(user=user, can_login=True, is_active=True, is_deleted=False, salon__is_active=True)
        .first()
    )


def _suggest_haircut(gender, face_shape, hair_texture, hair_length):
    if gender == "female":
        map_female = {
            "round": "Layered Lob with side partition",
            "square": "Soft textured waves with curtain bangs",
            "heart": "Chin-length bob with volume",
            "long": "Feather cut with face framing layers",
            "diamond": "Medium shag with side fringe",
            "oval": "Any premium layered cut",
        }
        base = map_female.get(face_shape, "Soft layered cut")
    else:
        map_male = {
            "round": "High fade with textured quiff",
            "square": "Classic side part taper",
            "heart": "Low fade with fringe",
            "long": "Crew cut with medium fade",
            "diamond": "Textured crop with tapered sides",
            "oval": "Pompadour fade or textured crop",
        }
        base = map_male.get(face_shape, "Taper fade with texture")
        if hair_length == "long":
            base = "Layered man bun / slick back undercut"
    if hair_texture in {"curly", "coily"}:
        base += " (curl definition finish)"
    return base


def _suggest_beard(gender, face_shape, beard_preference):
    if gender != "male":
        return "No beard styling required"
    if beard_preference == "clean":
        return "Clean shave with sharp neckline"
    if beard_preference == "stubble":
        return "3-day stubble with cheek line shaping"
    if beard_preference == "full":
        return "Full beard with sculpted jawline finish"
    if face_shape == "round":
        return "Boxed beard with sharper chin length"
    return "Classic boxed beard with taper"


def _suggest_skin_plan(skin_type):
    if skin_type == "oily":
        return "Charcoal deep-clean facial", "Salicylic exfoliating scrub"
    if skin_type == "dry":
        return "Hydra-nourish facial", "Cream-based gentle scrub"
    if skin_type == "combination":
        return "Balancing glow facial", "Gel micro-exfoliating scrub"
    if skin_type == "sensitive":
        return "Soothing aloe facial", "Enzyme mild scrub"
    return "Vitamin C radiance facial", "Rice-polish brightening scrub"


def _style_cards(consultation):
    is_male = consultation.gender == "male"
    cards = [
        {
            "title": consultation.suggested_haircut,
            "category": "Recommended Primary Cut",
            "image": static("salon/img/style_hero.svg"),
        },
        {
            "title": "Modern Fade + Texture" if is_male else "Soft Layered Volume",
            "category": "Alternative 1",
            "image": static("salon/img/style_alt_1.svg"),
        },
        {
            "title": "Classic Side Profile Cut" if is_male else "Elegant Bob Finish",
            "category": "Alternative 2",
            "image": static("salon/img/style_alt_2.svg"),
        },
    ]
    if is_male:
        cards.append(
            {
                "title": consultation.suggested_beard,
                "category": "Beard Suggestion",
                "image": static("salon/img/style_beard.svg"),
            }
        )
    cards.append(
        {
            "title": consultation.suggested_facial,
            "category": "Facial Suggestion",
            "image": static("salon/img/style_facial.svg"),
        }
    )
    return cards


def _save_suggestions(consultation):
    fallback_haircut = _suggest_haircut(
        consultation.gender,
        consultation.face_shape,
        consultation.hair_texture,
        consultation.hair_length,
    )
    fallback_beard = _suggest_beard(
        consultation.gender,
        consultation.face_shape,
        consultation.beard_preference,
    )
    fallback_facial, fallback_scrub = _suggest_skin_plan(consultation.skin_type)

    consultation.suggested_haircut = fallback_haircut
    consultation.suggested_beard = fallback_beard
    consultation.suggested_facial = fallback_facial
    consultation.suggested_scrub = fallback_scrub
    consultation.suggestion_source = "rule"

    openai_result = _openai_vision_style_analysis(consultation)
    if openai_result:
        consultation.suggested_haircut = openai_result.get("haircut") or fallback_haircut
        consultation.suggested_beard = openai_result.get("beard") or fallback_beard
        consultation.suggested_facial = openai_result.get("facial") or fallback_facial
        consultation.suggested_scrub = openai_result.get("scrub") or fallback_scrub
        consultation.suggestion_source = "openai"


def _extract_json_payload(text):
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return None


def _openai_vision_style_analysis(consultation):
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None

    model = (os.getenv("OPENAI_STYLE_ADVISOR_MODEL") or "gpt-4.1-mini").strip()
    image_path = getattr(consultation.reference_image, "path", "")
    if not image_path:
        return None

    try:
        with open(image_path, "rb") as fh:
            image_b64 = base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return None

    user_prompt = (
        "You are a professional salon stylist assistant. "
        "Analyze the customer's face/hair image and profile and return strict JSON only with keys: "
        "haircut, beard, facial, scrub. Keep each recommendation under 110 chars.\n"
        f"Profile: gender={consultation.gender}, face_shape={consultation.face_shape}, "
        f"hair_texture={consultation.hair_texture}, hair_length={consultation.hair_length}, "
        f"skin_type={consultation.skin_type}, beard_preference={consultation.beard_preference}, "
        f"notes={consultation.concern_notes or 'none'}"
    )
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"},
                ],
            }
        ],
        "max_output_tokens": 240,
    }

    req = urlrequest.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    output_text = data.get("output_text")
    if not output_text:
        output = data.get("output") or []
        chunks = []
        for item in output:
            for content in item.get("content") or []:
                text_value = content.get("text")
                if text_value:
                    chunks.append(text_value)
        output_text = "\n".join(chunks)

    json_payload = _extract_json_payload(output_text or "")
    if not json_payload:
        return None

    try:
        parsed = json.loads(json_payload)
    except json.JSONDecodeError:
        return None

    return {
        "haircut": str(parsed.get("haircut") or "").strip(),
        "beard": str(parsed.get("beard") or "").strip(),
        "facial": str(parsed.get("facial") or "").strip(),
        "scrub": str(parsed.get("scrub") or "").strip(),
    }


def _build_multipart_form(fields, file_field_name, file_name, file_bytes, content_type):
    boundary = f"----CodexStyleBoundary{uuid4().hex}"
    chunks = []
    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode("utf-8")
        )
    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(
        (
            f'Content-Disposition: form-data; name="{file_field_name}"; filename="{file_name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return boundary, b"".join(chunks)


def _openai_style_preview_image(consultation, selected_style):
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None, "OPENAI_API_KEY is missing."

    model = (os.getenv("OPENAI_STYLE_PREVIEW_MODEL") or "gpt-image-1").strip()
    image_path = getattr(consultation.reference_image, "path", "")
    image_name = getattr(consultation.reference_image, "name", "")
    if not image_path:
        return None, "Reference image file is not available."

    ext = os.path.splitext(image_name)[1].lower()
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")

    try:
        with open(image_path, "rb") as fh:
            source_bytes = fh.read()
    except OSError:
        return None, "Unable to read uploaded reference image."

    prompt = (
        "Create a realistic salon makeover preview using the same person's face and pose. "
        f"Apply style: {selected_style}. "
        "Keep identity, skin tone, and background natural. "
        "Do not add text, watermark, or logo."
    )
    fields = {
        "model": model,
        "prompt": prompt,
        "size": "1024x1024",
        "response_format": "b64_json",
    }
    boundary, body = _build_multipart_form(
        fields=fields,
        file_field_name="image",
        file_name=f"reference{ext or '.jpg'}",
        file_bytes=source_bytes,
        content_type=content_type,
    )

    req = urlrequest.Request(
        "https://api.openai.com/v1/images/edits",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            payload = json.loads(raw) if raw else {}
            api_message = (
                payload.get("error", {}).get("message")
                or payload.get("message")
                or raw[:300]
                or "Unknown HTTP error from OpenAI."
            )
        except Exception:
            api_message = "Failed to parse OpenAI error response."
        detail = f"OpenAI HTTP {exc.code}: {api_message}"
        logger.warning("Style preview generation failed for consultation %s: %s", consultation.id, detail)
        return None, detail
    except error.URLError as exc:
        detail = f"Network error while contacting OpenAI: {exc.reason}"
        logger.warning("Style preview generation failed for consultation %s: %s", consultation.id, detail)
        return None, detail
    except TimeoutError:
        detail = "OpenAI request timed out while generating preview image."
        logger.warning("Style preview generation failed for consultation %s: %s", consultation.id, detail)
        return None, detail
    except json.JSONDecodeError:
        detail = "OpenAI returned an unreadable response for preview image."
        logger.warning("Style preview generation failed for consultation %s: %s", consultation.id, detail)
        return None, detail

    image_data = ((data.get("data") or [{}])[0]).get("b64_json")
    if not image_data:
        detail = "OpenAI response did not include image data (b64_json)."
        logger.warning("Style preview generation failed for consultation %s: %s", consultation.id, detail)
        return None, detail
    try:
        return base64.b64decode(image_data), None
    except (ValueError, TypeError):
        detail = "OpenAI image payload could not be decoded."
        logger.warning("Style preview generation failed for consultation %s: %s", consultation.id, detail)
        return None, detail


def _render_style_page(request, salon, is_worker=False):
    consultations_qs = StyleConsultation.objects.filter(user=request.user, salon=salon).order_by("-created_at")
    selected = consultations_qs.first()
    selected_id = request.GET.get("consultation")
    if selected_id:
        selected = consultations_qs.filter(id=selected_id).first() or selected

    worker_profile = None
    if is_worker:
        worker_profile = Worker.objects.select_related("salon").filter(
            user=request.user, can_login=True, is_active=True, is_deleted=False
        ).first()

    consultations_page = request.GET.get("consultations_page") or "1"
    consultations = Paginator(consultations_qs, PAGE_SIZE).get_page(consultations_page)
    consultations_query_params = request.GET.copy()
    consultations_query_params.pop("consultations_page", None)

    form = StyleConsultationForm()
    if request.method == "POST":
        form_type = (request.POST.get("form_type") or "").strip()
        if form_type == "save_consultation":
            form = StyleConsultationForm(request.POST, request.FILES)
            if form.is_valid():
                entry = form.save(commit=False)
                entry.user = request.user
                entry.salon = salon
                _save_suggestions(entry)
                entry.save()
                messages.success(request, "AI style recommendation generated.")
                return redirect(f"{request.path}?consultation={entry.id}")
        elif form_type == "pick_style":
            entry = get_object_or_404(StyleConsultation, id=request.POST.get("consultation_id"), user=request.user, salon=salon)
            entry.selected_style = (request.POST.get("selected_style") or "").strip()[:160]
            update_fields = ["selected_style"]
            preview_bytes, preview_error = _openai_style_preview_image(entry, entry.selected_style)
            if preview_bytes:
                filename = f"style_preview_{entry.id}_{uuid4().hex[:10]}.png"
                entry.transformed_preview_image.save(filename, ContentFile(preview_bytes), save=False)
                update_fields.append("transformed_preview_image")
                messages.success(request, "Selected style saved and AI preview generated.")
            else:
                messages.warning(
                    request,
                    f"Selected style saved. AI preview image could not be generated: {preview_error or 'Unknown error.'}",
                )
            entry.save(update_fields=update_fields)
            return redirect(f"{request.path}?consultation={entry.id}")

    style_cards = _style_cards(selected) if selected else []
    return render(
        request,
        "salon/style_advisor.html",
        {
            "salon": salon,
            "form": form,
            "consultations": consultations,
            "selected_consultation": selected,
            "style_cards": style_cards,
            "is_worker_user": is_worker,
            "worker_profile": worker_profile,
            "consultations_querystring": consultations_query_params.urlencode(),
        },
    )


@login_required
def owner_style_advisor(request, slug):
    salon = get_object_or_404(Salon, slug=slug, owner=request.user, is_active=True)
    return _render_style_page(request, salon, is_worker=False)


@login_required
def worker_style_advisor(request):
    worker = _worker_for_user(request.user)
    if not worker:
        messages.error(request, "Worker access is not enabled for this account.")
        return redirect("owner_dashboard")
    return _render_style_page(request, worker.salon, is_worker=True)
    worker_profile = None
    if is_worker:
        worker_profile = Worker.objects.select_related("salon").filter(
            user=request.user, can_login=True, is_active=True, is_deleted=False
        ).first()
