// Central access-pack metadata — mirrors PACK_PERMS/PACK_LABEL in backend/server.py.
import { Crown, LineChart, DollarSign, Users2, Briefcase, Wrench, Shield } from "lucide-react";

export const PACKS = [
  { id: "owner", label: "Owner", icon: Crown, style: "text-gold bg-gold/10 border-gold/20", desc: "Full control — runs the company, billing & access." },
  { id: "exec", label: "Executive", icon: LineChart, style: "text-violet-300 bg-violet-400/10 border-violet-400/20", desc: "Full read + can decide and invite teammates (not owners)." },
  { id: "finance", label: "Finance", icon: DollarSign, style: "text-emerald-300 bg-emerald-400/10 border-emerald-400/20", desc: "Reads everything, writes financials." },
  { id: "hr", label: "People / HR", icon: Users2, style: "text-sky-300 bg-sky-400/10 border-sky-400/20", desc: "Reads everything, manages the roster & headcount." },
  { id: "sales", label: "Sales", icon: Briefcase, style: "text-amber-300 bg-amber-400/10 border-amber-400/20", desc: "Reads everything, owns pipeline (write loop coming)." },
  { id: "ops", label: "Operations", icon: Wrench, style: "text-teal-300 bg-teal-400/10 border-teal-400/20", desc: "Reads everything, owns ops & risks (write loop coming)." },
  { id: "member", label: "Member", icon: Shield, style: "text-zinc-300 bg-white/5 border-white/10", desc: "Read access + works their own tasks and posts a daily update." },
];

export const packMeta = (id) => PACKS.find((p) => p.id === id) || PACKS[PACKS.length - 1];
export const hasPerm = (user, perm) => Array.isArray(user?.perms) && user.perms.includes(perm);
