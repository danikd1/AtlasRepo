export interface RSSFeed {
  id: string;
  title: string;
  url: string;
  description?: string;
  addedAt?: string;          
  folderId?: string;
  sourceId?: string;         
  sourceName?: string;       
  hidden?: boolean;
  unread_count?: number;     
  favicon_url?: string;      
  error_count?: number;      
  last_error?: string;       
  category?: string;         
  feedIds?: number[];        
}

export interface Source {
  id: string;
  name: string; 
  domain: string; 
  description: string;
  iconType: string;
  createdAt: string;
}

export interface Folder {
  id: string;
  name: string;
  createdAt: string;
  sourceId?: string; 
  isSourceFolder?: boolean; 
}

export interface RSSArticle {
  id: string;
  feedId: string;
  feedTitle: string;
  title: string;
  link: string;
  description: string;
  content?: string;
  pubDate: string;
  author?: string;
  read: boolean;
  saved?: boolean;
}

export type ArticleSource =
  | { kind: "today" }
  | { kind: "unread" }
  | { kind: "saved" }
  | { kind: "all" }
  | {
      kind: "feed";
      feedId: string;
      feedIds?: number[]; 
      title: string;
      favicon_url?: string;
    }
  | {
      kind: "topic";
      collectionId: number;  
      title: string;
      keywords?: string;
    };

export function sourceKey(source: ArticleSource | null): string | null {
  if (!source) return null;
  if (source.kind === "feed") return `feed:${source.feedId}`;
  if (source.kind === "topic") return `topic:${source.collectionId}`;
  return source.kind;
}

export interface OutletCtx {
  selectedSource: ArticleSource | null;
  setSelectedSource: (source: ArticleSource | null) => void;
}