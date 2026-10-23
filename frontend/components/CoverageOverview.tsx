import Icon from "@/components/Icon";
import Link from "next/link";
import { getCoverage, regionSlug } from "@/lib/coverage";
export default async function CoverageOverview() {
  const c = await getCoverage();
  if (!c)
    return (
      <p className="field-help">
        See <Link href="/sources">current source coverage</Link>.
      </p>
    );
  return (
    <div className="health-panel">
      <h3>What you can find right now</h3>
      <p>
        {c.categories.jobs || 0} Ghana jobs · {c.categories.early || 0}{" "}
        early-career opportunities · {c.categories.remote || 0} Ghana-eligible
        remote roles · {c.categories.scholarships || 0} open study & research
        funding notices
      </p>
      <p>
        Counts change as sources publish and close opportunities. Region totals
        include jobs, early careers and remote roles with a mapped location,
        including nationwide programmes.
      </p>
      <div className="coverage-list">
        {Object.entries(c.regions).map(([name, count]) => (
          <Link key={name} href={`/regions/${regionSlug(name)}`}>
            {name} · {count}
          </Link>
        ))}
      </div>
      <Link className="portal-text-link" href="/sources">
        Check sources and freshness <Icon name="arrow-right" />
      </Link>
    </div>
  );
}
