export const regions = [
  "Greater Accra",
  "Ashanti",
  "Western",
  "Central",
  "Eastern",
  "Volta",
  "Northern",
  "Upper East",
  "Upper West",
  "Bono",
  "Bono East",
  "Ahafo",
  "Western North",
  "Oti",
  "North East",
  "Savannah",
];
export const categories = [
  ["jobs", "Jobs in Ghana"],
  ["early", "Early careers"],
  ["remote", "Remote from Ghana"],
  ["scholarships", "Scholarships & research"],
];
export const types: Record<string, string[][]> = {
  jobs: [
    ["all", "All jobs"],
    ["permanent", "Permanent"],
    ["full-time", "Full-time"],
    ["part-time", "Part-time"],
    ["contract", "Contracts"],
  ],
  early: [
    ["all", "All early careers"],
    ["internship", "Internships"],
    ["graduate", "Graduate programmes"],
    ["apprenticeship", "Apprenticeships"],
  ],
  remote: [
    ["all", "All remote roles"],
    ["permanent", "Permanent"],
    ["full-time", "Full-time"],
    ["part-time", "Part-time"],
    ["contract", "Contracts"],
    ["internship", "Internships"],
    ["graduate", "Graduate roles"],
    ["apprenticeship", "Apprenticeships"],
  ],
};
export const experienceLevels = [
  ["no-experience", "No experience required"],
  ["junior", "Junior / entry level"],
  ["mid", "Mid-level"],
  ["senior", "Senior / lead"],
  ["management", "Management"],
];
export const studyLevels = [
  ["undergraduate", "Undergraduate"],
  ["masters", "Master’s"],
  ["mphil", "MPhil"],
  ["phd", "PhD"],
  ["postdoc", "Postdoctoral research"],
];
export const scholarshipTypes = [
  ["all", "All funding opportunities"],
  ["scholarship", "Degree scholarships"],
  ["research-grant", "Research grants"],
  ["fellowship", "Fellowships"],
  ["research-award", "Research prizes & awards"],
  ["training", "Funded courses & training"],
  ["other-funding", "Other funding & exchanges"],
];
export const scholarshipSources = [
  ["scholarships-authority", "ScholSec / Scholarships Authority"],
  ["daad-ghana", "DAAD Ghana funding database"],
  ["ug-research", "University of Ghana research calls"],
  ["knust-research", "KNUST research calls"],
  ["lincoln-global-leaders", "University of Lincoln"],
  ["harvard-loeb", "Harvard Loeb Fellowship"],
  ["bodleian-visiting", "Oxford Bodleian Libraries"],
  ["columbia-italian-academy", "Columbia Italian Academy"],
  ["unesco-research-continuity", "UNESCO research grants"],
  ["ucl-hp-ai-education", "UCL funded leadership training"],
  ["lse-demography-funding", "LSE research studentships"],
];
export function displayDate(value?: string | number | null) {
  if (!value) return "Not provided";
  const d = new Date(typeof value === "number" ? value * 1000 : value);
  return Number.isNaN(d.getTime())
    ? "Not provided"
    : d.toLocaleDateString("en-GB", {
        timeZone: "Africa/Accra",
        day: "numeric",
        month: "short",
        year: "numeric",
      });
}
