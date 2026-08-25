const THEME_VARIABLES = {
  theme_primary_color: "--brand-primary",
  theme_secondary_color: "--brand-secondary",
  theme_soft_color: "--brand-soft",
  theme_nav_strip_background: "--nav-strip-background",
  theme_nav_strip_text: "--nav-strip-text",
  theme_footer_background: "--footer-background",
  theme_footer_text: "--footer-text",
  theme_footer_muted_text: "--footer-muted-text",
  theme_button_primary_background: "--button-primary-background",
  theme_button_primary_text: "--button-primary-text",
};

export const THEME_KEYS = Object.keys(THEME_VARIABLES);

export function buildStorefrontThemeVariables(settings = {}) {
  const variables = {};
  for (const [field, variable] of Object.entries(THEME_VARIABLES)) {
    if (settings[field]) variables[variable] = settings[field];
  }
  if (settings.theme_primary_color) variables["--brand-primary-hover"] = `color-mix(in srgb, ${settings.theme_primary_color} 82%, #000)`;
  if (settings.theme_button_primary_background) variables["--button-primary-hover"] = `color-mix(in srgb, ${settings.theme_button_primary_background} 82%, #000)`;
  return variables;
}

export function staticThemeDefaults() {
  const styles = getComputedStyle(document.documentElement);
  return Object.fromEntries(Object.entries(THEME_VARIABLES).map(([field, variable]) => [field, styles.getPropertyValue(variable).trim()]));
}

export function contrastRatio(first, second) {
  const luminance = (hex) => {
    const values = [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255).map((value) => value <= .03928 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return values[0] * .2126 + values[1] * .7152 + values[2] * .0722;
  };
  const [light, dark] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (light + .05) / (dark + .05);
}
