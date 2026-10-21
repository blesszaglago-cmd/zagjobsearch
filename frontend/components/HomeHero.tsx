"use client";
import Icon from "@/components/Icon";
import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
const slides = [
  {
    image: "/images/professionals.jpg",
    label: "Work",
    headline: "Ghanaian talent.",
    highlight: "Extraordinary possibilities.",
    description:
      "Discover jobs, internships and scholarships for your next chapter. Search with purpose. Apply at the source. Keep your progress in one place.",
    primary: "Find an opportunity",
    href: "/search",
    secondary: "Explore scholarships",
    secondaryHref: "/search?category=scholarships",
  },
  {
    image: "/images/ghana-students.jpg",
    label: "Study",
    headline: "Your ambition.",
    highlight: "A world of possibility.",
    description:
      "Explore Scholsec’s public scholarship notices, with separate study levels, destinations and deadline filters to help you find your route.",
    primary: "Explore scholarships",
    href: "/search?category=scholarships",
    secondary: "Find internships",
    secondaryHref: "/search?category=early&job_type=internship",
  },
  {
    image: "/images/career-desk.jpg",
    label: "Progress",
    headline: "Every application.",
    highlight: "One clear next step.",
    description:
      "Remember where you applied, keep your notes and follow your progress. Your job hunt deserves more than scattered links and forgotten tabs.",
    primary: "Open your tracker",
    href: "/tracker",
    secondary: "Create a free account",
    secondaryHref: "/signup",
  },
];
export default function HomeHero() {
  const [active, setActive] = useState(0);
  const [visited, setVisited] = useState([0]);
  function showSlide(index: number) {
    setVisited((previous) =>
      previous.includes(index) ? previous : [...previous, index],
    );
    setActive(index);
  }
  const slide = slides[active];
  return (
    <section
      className="portal-hero"
      aria-label="Discover your next opportunity"
      aria-roledescription="carousel"
    >
      <div className="portal-hero-images" aria-hidden="true">
        {slides.map((item, i) => (
          <div
            key={item.label}
            className={`portal-hero-image${i === active ? " active" : ""}`}
          >
            {visited.includes(i) && (
              <Image
                src={item.image}
                alt=""
                fill
                sizes="100vw"
                loading="eager"
                fetchPriority={i === 0 ? "high" : "auto"}
                style={{ objectPosition: i === 1 ? "65% 45%" : "70% 50%" }}
              />
            )}
          </div>
        ))}
      </div>
      <div className="portal-hero-shade" />
      <div className="shell portal-hero-inner">
        <div className="portal-hero-copy">
          <p className="portal-eyebrow">YOUR NEXT MOVE STARTS HERE</p>
          <div
            key={active}
            className="portal-hero-content"
            aria-live="polite"
            aria-atomic="true"
          >
            <h1>
              {slide.headline}
              <br />
              <span>{slide.highlight}</span>
            </h1>
            <p>{slide.description}</p>
            <div className="portal-actions">
              <Link className="portal-button gold" href={slide.href}>
                {slide.primary} <span aria-hidden="true"><Icon name="arrow-up-right" /></span>
              </Link>
              <Link className="portal-button ghost" href={slide.secondaryHref}>
                {slide.secondary}
              </Link>
            </div>
          </div>
        </div>
        <div className="portal-hero-controls">
          <button
            type="button"
            onClick={() =>
              showSlide((active + slides.length - 1) % slides.length)
            }
            aria-label="Previous slide"
          >
            <Icon name="chevron-left" />
          </button>
          <div className="portal-hero-dots">
            {slides.map((item, i) => (
              <button
                type="button"
                key={item.label}
                aria-label={`Show ${item.label.toLowerCase()} slide`}
                aria-pressed={active === i}
                onClick={() => showSlide(i)}
              >
                <span className="sr-only">{item.label}</span>
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() =>
              showSlide((active + 1) % slides.length)
            }
            aria-label="Next slide"
          >
            <Icon name="chevron-right" />
          </button>
        </div>
      </div>
      <div className="portal-hero-caption shell">
        <span>OPPORTUNITIES FOR GHANA</span>
        <span>Work · Study · Progress</span>
      </div>
    </section>
  );
}
