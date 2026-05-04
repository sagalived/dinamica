import type { CardPriority, CardStatus } from './logic';

export type AttachmentType = 'image' | 'video' | 'document';

export interface Attachment {
  id: string;
  filename: string;
  originalName: string;
  type: AttachmentType;
  contentType: string;
  url: string;
  uploadedAt: string;
}

export interface KanbanCard {
  id: string;
  sprintId: string;
  buildingId: string;
  title: string;
  description: string;
  status: CardStatus;
  priority: CardPriority;
  responsible: string;
  dueDate: string;
  tags: string[];
  attachments: Attachment[];
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface KanbanSprint {
  id: string;
  buildingId: string;
  name: string;
  startDate: string;
  endDate: string;
  color: string;
  createdAt: string;
  updatedAt: string;
  cards: KanbanCard[];
}

export interface CardModalProps {
  card: Partial<KanbanCard> | null;
  sprintId: string;
  buildingId: string;
  sessionUser: any;
  onClose: () => void;
  onSave: (card: Partial<KanbanCard>) => Promise<void>;
  onDelete?: () => Promise<void>;
  onUpload: (cardId: string, file: File) => Promise<Attachment | null>;
  onDeleteAttachment: (cardId: string, att: Attachment) => Promise<void>;
  isNew: boolean;
}

export type DiarioObrasProps = {
  buildingId: string;
  buildingName: string;
  sessionUser: any;
  buildings?: { id: number | string; name: string }[];
};
