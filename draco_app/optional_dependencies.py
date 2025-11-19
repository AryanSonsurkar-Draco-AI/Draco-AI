"""Helpers to load optional third-party dependencies used by Draco."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DocTools:
    Document: Optional[object]
    Presentation: Optional[object]
    Inches: Optional[object]
    Pt: Optional[object]
    PP_ALIGN: Optional[object]
    RGBColor: Optional[object]
    MSO_SHAPE: Optional[object]
    FPDF: Optional[object]
    PdfReader: Optional[object]


@dataclass
class RuntimeExtras:
    pyttsx3: Optional[object]
    pygame: Optional[object]
    speech_recognition: Optional[object]
    recognizer: Optional[object]
    psutil: Optional[object]
    pyautogui: Optional[object]
    pywhatkit: Optional[object]
    DDGS: Optional[object]
    musicLibrary: Optional[object]


def load_doc_tools() -> DocTools:
    try:
        from docx import Document  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        Document = None

    try:
        from pptx import Presentation  # type: ignore
        from pptx.util import Inches, Pt  # type: ignore
        from pptx.enum.text import PP_ALIGN  # type: ignore
        from pptx.dml.color import RGBColor  # type: ignore
        from pptx.enum.shapes import MSO_SHAPE  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        Presentation = None
        Inches = Pt = PP_ALIGN = RGBColor = MSO_SHAPE = None

    try:
        from fpdf import FPDF  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        FPDF = None

    try:
        from PyPDF2 import PdfReader  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        PdfReader = None

    return DocTools(
        Document=Document,
        Presentation=Presentation,
        Inches=Inches,
        Pt=Pt,
        PP_ALIGN=PP_ALIGN,
        RGBColor=RGBColor,
        MSO_SHAPE=MSO_SHAPE,
        FPDF=FPDF,
        PdfReader=PdfReader,
    )


def load_runtime_extras() -> RuntimeExtras:
    try:
        import pyttsx3  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        pyttsx3 = None

    try:
        import pygame  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        pygame = None

    try:
        import speech_recognition as sr  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        sr = None

    recognizer = None
    if sr:
        try:
            recognizer = sr.Recognizer()
        except Exception:
            recognizer = None

    try:
        import psutil  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        psutil = None

    try:
        import pyautogui  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        pyautogui = None

    try:
        import pywhatkit  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        pywhatkit = None

    try:
        from ddgs import DDGS  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        DDGS = None

    try:
        import musicLibrary  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        musicLibrary = None

    return RuntimeExtras(
        pyttsx3=pyttsx3,
        pygame=pygame,
        speech_recognition=sr,
        recognizer=recognizer,
        psutil=psutil,
        pyautogui=pyautogui,
        pywhatkit=pywhatkit,
        DDGS=DDGS,
        musicLibrary=musicLibrary,
    )


__all__ = ["DocTools", "RuntimeExtras", "load_doc_tools", "load_runtime_extras"]
