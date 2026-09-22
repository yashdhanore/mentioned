import {
  ArrowLeft,
  Ellipsis,
  ExternalLink,
  MapPin,
  Plus,
  Tag,
  User,
  type LucideProps,
} from 'lucide-react-native';

import { colors } from '@/theme';

type IconProps = {
  color?: string;
  size?: number;
};

const defaultIconProps = {
  absoluteStrokeWidth: true,
  strokeWidth: 2,
} satisfies Pick<LucideProps, 'absoluteStrokeWidth' | 'strokeWidth'>;

function iconProps(color: string, size = 22): LucideProps {
  return {
    ...defaultIconProps,
    color,
    size,
  };
}

export function PlusIcon({ color = colors.ink, size }: IconProps) {
  return <Plus {...iconProps(color, size)} />;
}

export function UserIcon({ color = colors.ink, size }: IconProps) {
  return <User {...iconProps(color, size)} />;
}

export function BackIcon({ color = colors.ink, size }: IconProps) {
  return <ArrowLeft {...iconProps(color, size)} />;
}

export function MoreIcon({ color = colors.ink, size }: IconProps) {
  return <Ellipsis {...iconProps(color, size)} />;
}

export function ExternalLinkIcon({ color = colors.ink, size }: IconProps) {
  return <ExternalLink {...iconProps(color, size)} />;
}

export function PlaceIcon({ color = colors.ink, size }: IconProps) {
  return <MapPin {...iconProps(color, size)} />;
}

export function ProductIcon({ color = colors.ink, size }: IconProps) {
  return <Tag {...iconProps(color, size)} />;
}
