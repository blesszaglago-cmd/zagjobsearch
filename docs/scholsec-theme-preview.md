# Scholsec-style photo theme preview

Design reference: https://scholarships.gov.gh/ (reviewed 17 October 2026).

This branch prepares the requested visual redesign for review before promotion to the production branch. It follows the reference's full-width photographic hero, dark green overlay, gold actions, Lato/Raleway typography, opportunity cards, route sections, layered photographs, application journey and dark footer. ZagJobSearch retains its ZB identity and existing search, account and application workflows.

The supplied Ghana flag and kente artwork remain local assets. Kente is used on thin borders instead of the former large patterned frame. Every homepage section has visible photography or a subtle photographic background. The same treatment carries into search, details, authentication and the tracker. Responsive rules cover small phones, tablets and desktop. Transitions respect prefers-reduced-motion; the hero uses manual controls and never auto-advances.

The homepage's featured opportunities use existing public catalogue endpoints. They never fabricate roles or turn unavailable scholarships into open awards. A source failure has an honest fallback to search. These changes add no paid API or image service.

## New photo assets

- `frontend/public/images/professionals.jpg`: WOCInTech, https://nappy.co/photo/wocintech-microsoft-225+K_HF7htJUu_2JlJ3sPocz. Nappy CC0/public-domain license: https://nappy.co/license. Used as illustrative professional photography, without claiming Ghanaian location or endorsement.
- `frontend/public/images/ghana-students.jpg`: Creab ThePolymath, Ghanaian students in Accra, https://unsplash.com/photos/jDXMQf3LPX8. Unsplash License: https://unsplash.com/license.
- Existing local office/team photographs are retained; original image URLs are recorded in `docs/redesign-preview.md`.
- All photos are served locally. No Google Fonts or stock-photo services are contacted by a visitor's browser.
- Lato and Raleway are self-hosted under the accompanying SIL Open Font Licenses in `frontend/public/fonts`.

Photography credits appear in the footer. ZagJobSearch is identified as an independent platform; no government logo or official-agency claim is introduced.

## Validation

Production build and TypeScript check; static homepage rendering, asset references, carousel accessibility labels, and retained Google/Bing verification metadata. Interactive browser QA is unavailable in this session because the required control-browser capability is not exposed. Review the Vercel branch preview, including the hero controls, phone layout, real listing links, filters and signed-in tracker, before production promotion.
