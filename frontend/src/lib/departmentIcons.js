/** Icon map for department catalog icon slugs. */
import {
  Package, Factory, Landmark, Briefcase, Scale, Users, Wrench, Building2,
} from "lucide-react";

export const DEPT_ICONS = {
  package: Package,
  factory: Factory,
  landmark: Landmark,
  briefcase: Briefcase,
  scale: Scale,
  users: Users,
  wrench: Wrench,
};

export function departmentIcon(slug) {
  return DEPT_ICONS[slug] || Building2;
}
