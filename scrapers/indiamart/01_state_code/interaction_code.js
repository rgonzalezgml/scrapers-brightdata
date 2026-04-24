// interaction — dispatcher
const CATEGORIES = {
    mcat: [
        "caustic-soda",
        "sodium-hydroxide-pellets",
        "hydrochloric-acid",
        "sulphuric-acid",
        "sodium-carbonate",
        "acetic-acid",
        "industrial-drums",
        "industrial-containers",
        "plastic-drums",
        "corrugated-box",
        "packaging-materials",
        "stretch-film",
    ],
    hub: [
        "chem",
        "packaging",
    ],
};

if (input.category_slug) {
    // Categoría específica → pasar directo al Stage 2
    next_stage({
        category_slug: input.category_slug,
        kind: input.kind || 'mcat'
    });
} else {
    // Sin categoría → fan-out de todas

    // for (const slug of CATEGORIES.mcat) {
    //     next_stage({ category_slug: slug, kind: 'mcat', url: input.url });
    // }
    // for (const slug of CATEGORIES.hub) {
    //     next_stage({ category_slug: slug, kind: 'hub', url: input.url });
    // }

    const categories = CATEGORIES[input.kind] ?? []
    for (const slug of categories) {
        next_stage({ category_slug: slug, kind: 'mcat', url: input.url });
    }
}