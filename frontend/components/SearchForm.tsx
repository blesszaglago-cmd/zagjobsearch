import Icon from "@/components/Icon";
import { regions } from "@/lib/ghana";
export default function SearchForm() {
  return (
    <form action="/search" className="home-search" role="search">
      <input type="hidden" name="category" value="jobs" />
      <label className="keyword-field">
        <span aria-hidden="true"><Icon name="search" /></span>
        <span className="sr-only">Job title or keywords</span>
        <input name="q" placeholder="Job title, company or skill" />
      </label>
      <label className="country-field">
        <span className="sr-only">Region in Ghana</span>
        <select name="region" defaultValue="">
          <option value="">Across Ghana</option>
          {regions.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </label>
      <button className="btn-primary" type="submit">
        Search Ghana <span aria-hidden="true"><Icon name="arrow-up-right" /></span>
      </button>
    </form>
  );
}
