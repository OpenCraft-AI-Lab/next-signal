import { ActiveIngests } from "@/components/knowledge/active-ingests";
import { IngestForm } from "@/components/knowledge/ingest-form";
import { ReindexButton } from "@/components/knowledge/reindex-button";
import { ResizableSidebar } from "@/components/knowledge/resizable-sidebar";
import { SearchResults } from "@/components/knowledge/search-results";
import { SidebarTree } from "@/components/knowledge/sidebar-tree";
import { MarkdownText } from "@/components/radar/markdown-text";
import { Input } from "@/components/ui/input";
import { searchKnowledge } from "@/lib/actions/knowledge";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
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

  const [tree, hits, active] = await Promise.all([
    listWikiTree(),
    q ? searchKnowledge(q) : Promise.resolve([]),
    docId ? getWikiDoc(docId) : Promise.resolve(null),
  ]);

  // Degrade to auto-classify-only if the taxonomy can't be read, so the rest
  // of the page (search / tree / preview) keeps working — mirrors lib/wiki.ts.
  let categories: WikiCategoryOption[] = [];
  try {
    categories = await listCategories();
  } catch {
    categories = [];
  }

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

              <div className="card" style={{ padding: 18, alignSelf: "start" }}>
                {active ? (
                  <ActivePreview doc={active} t={t} />
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
  t,
}: {
  doc: ActiveDoc;
  t: ReturnType<typeof getDictionary>;
}) {
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
        {doc.tags.map((t) => (
          <span key={t} className="chip tag">
            {t}
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
      <FrontmatterPanel data={doc.frontmatter} />
      <MarkdownText className="knowledge-markdown">{doc.body}</MarkdownText>
      {/* Edit / Open-full actions were in the design mock but are aspirational —
          they need an editor-protocol handshake (Edit) and a `/knowledge/[id]`
          full-page view (Open). Out of scope for foundation; revisit when that
          full-doc page lands. Leaving them out beats shipping dead buttons. */}
    </div>
  );
}

function FrontmatterPanel({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([, value]) => value != null);
  if (entries.length === 0) return null;

  return (
    <div className="frontmatter-panel">
      {entries.map(([key, value]) => (
        <div key={key} className="frontmatter-row">
          <span className="frontmatter-key">{key}</span>
          <FrontmatterValue value={value} />
        </div>
      ))}
    </div>
  );
}

function FrontmatterValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    return (
      <span className="frontmatter-value frontmatter-list">
        {value.map((item, index) => (
          <span key={`${String(item)}-${index}`} className="chip">
            {formatFrontmatterValue(item)}
          </span>
        ))}
      </span>
    );
  }

  return (
    <span className="frontmatter-value">{formatFrontmatterValue(value)}</span>
  );
}

function formatFrontmatterValue(value: unknown): string {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
