import { motion } from "framer-motion";
import { DEPARTMENTS_SECTION } from "@/lib/marketingCopy";
import { departmentIcon } from "@/lib/departmentIcons";

const ease = [0.16, 1, 0.3, 1];
const fade = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.06 } }),
};

/** Department lanes — used on Landing and Features. */
export default function DepartmentsShowcase({ compact = false }) {
  const { label, title, intro, items } = DEPARTMENTS_SECTION;
  const maxWidth = compact ? "max-w-4xl" : "max-w-6xl";

  return (
    <section className="px-6 py-24 border-t border-helm-cream/[0.05]">
      <div className={`mx-auto ${maxWidth}`}>
        <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }}>
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-helm-gold">{label}</p>
          <h2 className="font-display mt-4 text-3xl md:text-4xl font-medium tracking-tight max-w-2xl leading-tight">{title}</h2>
          <p className="mt-4 text-helm-slate max-w-2xl leading-relaxed">{intro}</p>
        </motion.div>
        <div className="mt-12 grid sm:grid-cols-2 border-l border-t border-helm-cream/[0.08]">
          {items.map((dept, i) => {
            const Icon = departmentIcon(dept.icon);
            return (
              <motion.div
                key={dept.name}
                variants={fade}
                custom={i}
                initial="hidden"
                whileInView="show"
                viewport={{ once: true, margin: "-60px" }}
                className="group border-b border-r border-helm-cream/[0.08] bg-helm-ink-card/40 p-6 transition-colors hover:bg-helm-cream/[0.03]"
              >
                <div className="flex items-start gap-4">
                  <div className="w-9 h-9 border border-helm-gold/25 flex items-center justify-center shrink-0">
                    <Icon className="w-5 h-5 text-helm-gold" aria-hidden />
                  </div>
                  <div>
                    <h3 className="text-lg text-helm-cream tracking-tight">{dept.name}</h3>
                    <p className="mt-1.5 text-sm text-helm-slate leading-relaxed">{dept.body}</p>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
