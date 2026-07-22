import { ActiveIngests } from "@/components/knowledge/active-ingests";
import { IngestForm } from "@/components/knowledge/ingest-form";
import { ReindexButton } from "@/components/knowledge/reindex-button";
import { ResizableSidebar } from "@/components/knowledge/resizable-sidebar";
import { ReviewSection } from "@/components/knowledge/review-section";
import { SearchResults } from "@/components/knowledge/search-results";
import { SidebarTree } from "@/components/knowledge/sidebar-tree";
import { MarkdownText } from "@/components/radar/markdown-text";
import { Input } from "@/components/ui/input";
import { searchKnowledge } from "@/lib/actions/knowledge";
import { getDictionary, type Locale } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
import { getTagLabels } from "@/lib/knowledge/tag-labels";
import { getDueReviews } from "@/lib/knowledge/review";
import { listCategories, type WikiCategoryOption } from "@/lib/taxonomy";
import { getWikiDoc, listWikiTree } from "@/lib/wiki";

type SearchParams = { q?: string; doc?: string };

export default async function KnowledgePage({
  searchParams,
}: {
  searchParams?: Promise<SearchParams>;
}) {
  const params = (await searchParams) ?? {};
  const locale = await getLocale();
  const t = getDictionary(locale);
  const q = (params.q ?? "").trim();
  const docId = params.doc;

  const [tree, hits, active, reviews] = await Promise.all([
    listWikiTree(),
    q ? searchKnowledge(q) : Promise.resolve([]),
    docId ? getWikiDoc(docId) : Promise.resolve(null),
    // Degrade to an empty review section if Postgres is unreachable, so the rest
    // of the page (tree / search / preview, all filesystem + GBrain) still works.
    getDueReviews().catch(() => ({ cards: [], total: 0 })),
  ]);

  // Degrade to auto-classify-only if the taxonomy can't be read, so the rest
  // of the page (search / tree / preview) keeps working — mirrors lib/wiki.ts.
  let categories: WikiCategoryOption[] = [];
  try {
    categories = await listCategories();
  } catch {
    categories = [];
  }

  // Per-item locale drives the preview's chrome (labels / headings / tag labels),
  // NOT the UI cookie — so each artifact renders whole in its own language. Falls
  // back to the UI locale for legacy docs with no `locale` stamp.
  const rawLocale = active ? active.frontmatter.locale : undefined;
  const itemLocale: Locale =
    rawLocale === "zh" || rawLocale === "en" ? rawLocale : locale;
  const tagLabels = active
    ? await getTagLabels(active.tags, itemLocale)
    : new Map<string, string>();

  return (
    <div className="page page-enter">
      <div className="shell">
        <div
          className="row"
          style={{
            justifyContent: "space-between",
            alignItems: "flex-end",
            marginBottom: 18,
          }}
        >
          <div>
            <h1 className="page-title">{t.knowledge.title}</h1>
            <p className="page-sub">{t.knowledge.subtitle}</p>
          </div>
          <ReindexButton />
        </div>

        <ReviewSection reviews={reviews} t={t} />

        <div className="card" style={{ padding: 16, marginBottom: 18 }}>
          <div className="col gap-12">
            <IngestForm categories={categories} />
            <ActiveIngests />
          </div>
        </div>

        <div className="knowgrid">
          <ResizableSidebar>
            <SidebarTree tree={tree} selectedId={active?.id} q={q} />
          </ResizableSidebar>

          <div className="col gap-16">
            <form action="/knowledge" method="get" className="search-wrap">
              {docId && <input type="hidden" name="doc" value={docId} />}
              <Input
                name="q"
                defaultValue={q}
                placeholder={t.knowledge.searchPlaceholder}
                style={{ height: 38, fontSize: 14 }}
              />
            </form>

            <div className={q ? "knowmain" : "knowmain knowmain-single"}>
              <SearchResults hits={hits} q={q} selectedSlug={docId} />

              <div
                id="doc-preview"
                className="card"
                style={{ padding: 18, alignSelf: "start", scrollMarginTop: 80 }}
              >
                {active ? (
                  <ActivePreview
                    doc={active}
                    locale={itemLocale}
                    tagLabels={tagLabels}
                  />
                ) : (
                  <span className="muted">
                    {q && hits.length > 0
                      ? t.knowledge.clickResult
                      : t.knowledge.selectDoc}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

type ActiveDoc = NonNullable<Awaited<ReturnType<typeof getWikiDoc>>>;

function ActivePreview({
  doc,
  locale,
  tagLabels,
}: {
  doc: ActiveDoc;
  locale: Locale;
  tagLabels: Map<string, string>;
}) {
  // The whole preview renders in the item's own locale so it reads as one
  // coherent language, regardless of the viewer's UI cookie.
  const t = getDictionary(locale);
  return (
    <div className="col" style={{ gap: 12 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="eyebrow">{t.knowledge.preview}</span>
        <span className="mono muted-2" style={{ fontSize: 11 }}>
          {doc.id}
        </span>
      </div>
      <h3
        style={{
          margin: 0,
          fontSize: 18,
          fontWeight: 600,
          letterSpacing: "-0.025em",
        }}
      >
        {doc.title}
      </h3>
      <div className="row gap-6 wrap">
        {doc.tags.map((tag) => (
          <span key={tag} className="chip tag">
            {tagLabels.get(tag) ?? tag}
          </span>
        ))}
        <span
          className="mono muted-2"
          style={{ fontSize: 11, alignSelf: "center" }}
        >
          · {t.knowledge.updated(doc.updated)}
        </span>
      </div>
      <hr className="hr" />
      <FrontmatterPanel data={doc.frontmatter} t={t} tagLabels={tagLabels} />
      <MarkdownText className="knowledge-markdown" headingLocale={locale}>
        {doc.body}
      </MarkdownText>
      {/* Edit / Open-full actions were in the design mock but are aspirational —
          they need an editor-protocol handshake (Edit) and a `/knowledge/[id]`
          full-page view (Open). Out of scope for foundation; revisit when that
          full-doc page lands. Leaving them out beats shipping dead buttons. */}
    </div>
  );
}

function FrontmatterPanel({
  data,
  t,
  tagLabels,
}: {
  data: Record<string, unknown>;
  t: ReturnType<typeof getDictionary>;
  tagLabels: Map<string, string>;
}) {
  const entries = Object.entries(data).filter(([, value]) => value != null);
  if (entries.length === 0) return null;

  // Localize the field-name labels by the item locale; the stored YAML keys
  // themselves stay English (a machine contract) — this is display only.
  const keyLabels = t.knowledge.frontmatter.keys as Record<string, string>;

  return (
    <div className="frontmatter-panel">
      {entries.map(([key, value]) => (
        <div key={key} className="frontmatter-row">
          <span className="frontmatter-key">{keyLabels[key] ?? key}</span>
          <FrontmatterValue
            fieldKey={key}
            value={value}
            t={t}
            tagLabels={tagLabels}
          />
        </div>
      ))}
    </div>
  );
}

function FrontmatterValue({
  fieldKey,
  value,
  t,
  tagLabels,
}: {
  fieldKey: string;
  value: unknown;
  t: ReturnType<typeof getDictionary>;
  tagLabels: Map<string, string>;
}) {
  if (Array.isArray(value)) {
    return (
      <span className="frontmatter-value frontmatter-list">
        {value.map((item, index) => {
          const text = formatFrontmatterValue(item);
          // Tag keys stay English in storage; show the localized display alias.
          const shown = fieldKey === "tags" ? (tagLabels.get(text) ?? text) : text;
          return (
            <span key={`${text}-${index}`} className="chip">
              {shown}
            </span>
          );
        })}
      </span>
    );
  }

  return (
    <span className="frontmatter-value">
      {localizeEnumValue(fieldKey, formatFrontmatterValue(value), t)}
    </span>
  );
}

/** Map an English enum token (status/freshness/source_type/converter/locale) to
 * its localized label; non-enum values (dates, URLs, digest) render as-is. */
function localizeEnumValue(
  fieldKey: string,
  value: string,
  t: ReturnType<typeof getDictionary>,
): string {
  const values = t.knowledge.frontmatter.values as Record<
    string,
    Record<string, string>
  >;
  return values[fieldKey]?.[value] ?? value;
}

function formatFrontmatterValue(value: unknown): string {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
