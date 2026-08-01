import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";

export const SUPPORTED_LANGUAGES = [
  { code: "en", label: "English", dir: "ltr" as const },
] as const;

export type SupportedLanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

export function isRtl(code: string): boolean {
  void code;
  return false;
}

export function applyDocumentDirection(code: string): void {
  if (typeof document === "undefined") return;
  void code;
  document.documentElement.setAttribute("dir", "ltr");
  document.documentElement.setAttribute("lang", "en");
}

i18n.on("languageChanged", (lng) => {
  applyDocumentDirection(lng);
});

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
    },
    initAsync: false,
    fallbackLng: "en",
    lng: "en",
    supportedLngs: ["en"],
    interpolation: { escapeValue: false },
  });

applyDocumentDirection("en");
i18n.on("initialized", () => {
  applyDocumentDirection("en");
});

export default i18n;
