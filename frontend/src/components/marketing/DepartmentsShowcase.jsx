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
    <section className="px-6 py-24 border-t border-white/[0.05]">
      <div className={`mx-auto ${maxWidth}`}>
        <motion.div variants={fade} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-100px" }}>
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-gold">{label}</p>
          <h2 className="mt-4 text-3xl md:text-4xl font-light tracking-tight max-w-2xl leading-tight">{title}</h2>
          <p className="mt-4 text-zinc-400 max-w-2xl leading-relaxed">{intro}</p>
        </motion.div>
        <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
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
                className="group rounded-2xl border border-white/[0.06] bg-[#121214]/60 p-6 transition-colors hover:border-gold/25"
              >
                <div className="flex items-start gap-4">
                  <div className="w-11 h-11 rounded-lg bg-gold/10 border border-gold/25 flex items-center justify-center shrink-0">
                    <Icon className="w-5 h-5 text-gold" aria-hidden />
                  </div>
                  <div>
                    <h3 className="text-lg text-white tracking-tight">{dept.name}</h3>
                    <p className="mt-1.5 text-sm text-zinc-400 leading-relaxed">{dept.body}</p>
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
