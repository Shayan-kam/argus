import { useEffect } from "react";

function ScrollReveal() {
    useEffect(() => {
        const root = document.querySelector(".app-shell");

        if (!root) {
            return undefined;
        }

        const reduceMotion = window.matchMedia(
            "(prefers-reduced-motion: reduce)"
        ).matches;

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) {
                        return;
                    }

                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                });
            },
            {
                threshold: 0.14,
                rootMargin: "0px 0px -8% 0px"
            }
        );

        const watch = () => {
            root.querySelectorAll("[data-reveal]:not(.is-visible)").forEach((node) => {
                if (reduceMotion) {
                    node.classList.add("is-visible");
                    return;
                }

                observer.observe(node);
            });
        };

        watch();

        const mutations = new MutationObserver(watch);
        mutations.observe(root, {
            childList: true,
            subtree: true
        });

        return () => {
            mutations.disconnect();
            observer.disconnect();
        };
    }, []);

    return null;
}

export default ScrollReveal;
