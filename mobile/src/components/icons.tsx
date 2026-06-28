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

export function PlusIcon({ color = '#101A17', size }: IconProps) {
  return <Plus {...iconProps(color, size)} />;
}

export function UserIcon({ color = '#101A17', size }: IconProps) {
  return <User {...iconProps(color, size)} />;
}

export function BackIcon({ color = '#101A17', size }: IconProps) {
  return <ArrowLeft {...iconProps(color, size)} />;
}

export function MoreIcon({ color = '#101A17', size }: IconProps) {
  return <Ellipsis {...iconProps(color, size)} />;
}

export function ExternalLinkIcon({ color = '#101A17', size }: IconProps) {
  return <ExternalLink {...iconProps(color, size)} />;
}

export function PlaceIcon({ color = '#101A17', size }: IconProps) {
  return <MapPin {...iconProps(color, size)} />;
}

export function ProductIcon({ color = '#101A17', size }: IconProps) {
  return <Tag {...iconProps(color, size)} />;
}
