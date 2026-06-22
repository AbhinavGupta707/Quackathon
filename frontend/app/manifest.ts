import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Afferens Memory Guardian",
    short_name: "Memory Guardian",
    description: "Evidence-backed home memory assistance for patient and caregiver review.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f5f7fb",
    theme_color: "#11695f",
    orientation: "portrait-primary",
    categories: ["health", "productivity", "utilities"],
    shortcuts: [
      {
        name: "Caregiver Review",
        short_name: "Caregiver",
        description: "Open the caregiver review queue.",
        url: "/caregiver"
      }
    ]
  };
}
