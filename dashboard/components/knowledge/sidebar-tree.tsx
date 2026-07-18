"use client";

import {
  ChevronDown,
  ChevronRight,
  File as FileIcon,
  Folder,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useI18n } from "@/components/i18n-provider";
import { DeleteConfirm } from "@/components/knowledge/delete-confirm-dialog";
import { NewFolderDialog } from "@/components/knowledge/new-folder-dialog";
import { deleteWikiDoc, deleteWikiFolder } from "@/lib/actions/knowledge";
import type { Locale } from "@/lib/i18n/dictionaries";
import { cn } from "@/lib/utils";
import type { WikiNode } from "@/lib/wiki";

interface SidebarTreeProps {
  tree: WikiNode[];
  /** Currently-previewed doc id (from `?doc=` query param). */
  selectedId?: string;
  /** Carry-through query so doc clicks preserve the active search. */
  q?: string;
}

const INDENT_STEP = 13;

/**
 * Wiki folder/doc tree. Folders collapse client-side; doc clicks navigate via
 * `<Link href="?q=...&doc=<id>">` so the server-rendered preview updates without
 * a full reload. Each row carries a hover-revealed delete action behind a
 * confirm dialog. A "New folder" button sits in the header.
 */
export function SidebarTree({ tree, selectedId, q }: SidebarTreeProps) {
  const { locale, t } = useI18n();

  return (
    <div className="card" style={{ padding: 10, alignSelf: "start" }}>
      <div
        className="row"
        style={{ justifyContent: "space-between", alignItems: "center" }}
      >
        <span className="eyebrow" style={{ padding: "4px 8px" }}>
          {t.knowledge.directory}
        </span>
        <NewFolderDialog />
      </div>
      <div className="col" style={{ marginTop: 4 }}>
        <Nodes
          nodes={tree}
          depth={0}
          selectedId={selectedId}
          q={q}
          locale={locale}
        />
      </div>
    </div>
  );
}

function Nodes({
  nodes,
  depth,
  selectedId,
  q,
  locale,
}: {
  nodes: WikiNode[];
  depth: number;
  selectedId?: string;
  q?: string;
  locale: Locale;
}) {
  return (
    <>
      {nodes.map((node) =>
        node.kind === "folder" ? (
          <FolderRow
            key={`d:${node.path}`}
            node={node}
            depth={depth}
            selectedId={selectedId}
            q={q}
            locale={locale}
          />
        ) : (
          <DocRow
            key={`f:${node.doc.id}`}
            doc={node.doc}
            depth={depth}
            selectedId={selectedId}
            q={q}
            locale={locale}
          />
        ),
      )}
    </>
  );
}

function FolderRow({
  node,
  depth,
  selectedId,
  q,
  locale,
}: {
  node: Extract<WikiNode, { kind: "folder" }>;
  depth: number;
  selectedId?: string;
  q?: string;
  locale: Locale;
}) {
  const { t } = useI18n();
  const m = t.knowledge.manage;
  const [open, setOpen] = useState(true);

  return (
    <div>
      <div className="treerow">
        <button
          className="treecat"
          onClick={() => setOpen((v) => !v)}
          style={{ paddingLeft: 8 + depth * INDENT_STEP }}
        >
          {open ? (
            <ChevronDown size={13} className="muted-2" />
          ) : (
            <ChevronRight size={13} className="muted-2" />
          )}
          <Folder size={14} className="muted" />
          <span className="elip" style={{ fontWeight: 500 }}>
            {node.name}
          </span>
          <span className="mono muted-2" style={{ fontSize: 11 }}>
            {node.docCount}
          </span>
        </button>
        <DeleteConfirm
          title={m.deleteFolderTitle}
          body={m.deleteFolderBody(node.name, node.docCount)}
          action={() => deleteWikiFolder(node.path, locale)}
        >
          <button className="treeact" aria-label={m.deleteFolder}>
            <Trash2 size={13} />
          </button>
        </DeleteConfirm>
      </div>
      <div className={cn("collapsible", open && "open")}>
        <div className="inner">
          <Nodes
            nodes={node.children}
            depth={depth + 1}
            selectedId={selectedId}
            q={q}
            locale={locale}
          />
        </div>
      </div>
    </div>
  );
}

function DocRow({
  doc,
  depth,
  selectedId,
  q,
  locale,
}: {
  doc: Extract<WikiNode, { kind: "doc" }>["doc"];
  depth: number;
  selectedId?: string;
  q?: string;
  locale: Locale;
}) {
  const { t } = useI18n();
  const m = t.knowledge.manage;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("doc", doc.id);

  return (
    <div className="treerow">
      <Link
        href={`/knowledge?${params.toString()}`}
        className={cn("treedoc", selectedId === doc.id && "on")}
        style={{ paddingLeft: 12 + depth * INDENT_STEP }}
      >
        <FileIcon size={13} className="muted-2" />
        <span className="elip">{doc.title}</span>
      </Link>
      <DeleteConfirm
        title={m.deleteFileTitle}
        body={m.deleteFileBody(doc.title)}
        action={() => deleteWikiDoc(doc.id, locale)}
      >
        <button className="treeact" aria-label={m.deleteFile}>
          <Trash2 size={13} />
        </button>
      </DeleteConfirm>
    </div>
  );
}
