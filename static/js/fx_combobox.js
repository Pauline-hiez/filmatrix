/* Sélecteurs enrichis « combobox » — moteur : FlyonUI (dist/combobox.js,
   copie vendored de node_modules, MIT).

   Chaque <select data-combobox> garde son rôle de source de vérité : le JS
   le masque (sr-only) et affiche à sa place un champ recherchable qui le
   reflète dans les deux sens. Tout le code existant qui lit select.value ou
   écoute l'événement change continue donc de fonctionner sans modification :
   - les options disabled/hidden en cours de route (disponibilité des tags
     côté préparation de partie) sont suivies via un MutationObserver ;
   - les assignations programmatiques de select.value (formulaires admin)
     mettent à jour l'affichage via un intercepteur.
   La recherche est insensible aux accents et aux majuscules, et accepte les
   mots dans n'importe quel ordre (« game thrones » trouve « Game of
   Thrones ») — c'est ce qui rend les longues listes vraiment fluides.
   Aucune dépendance au CSS FlyonUI : l'habillage vient de fx-select-* dans
   input.css, aux couleurs du site. */
(function () {
    "use strict";

    // Normalisation pour la recherche : minuscules sans accents. Les
    // diacritiques sont décomposés puis retirés, donc « é » devient « e »,
    // « Ça » devient « ca »… côté saisie comme côté options.
    function normalize(text) {
        return text
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim();
    }

    // Tous les mots saisis doivent exister dans l'option, dans n'importe
    // quel ordre : le joueur peut taper « trône game » ou « star wars ».
    function matchesSearch(normalizedHaystack, rawQuery) {
        return rawQuery
            .split(/\s+/)
            .filter(Boolean)
            .every(function (word) {
                return normalize(word) !== "" && normalizedHaystack.indexOf(normalize(word)) !== -1;
            });
    }

    // Remplace le filtrage natif (sous-chaîne simple, sensible aux accents)
    // par la recherche normalisée ci-dessus, sur l'attribut porté par les
    // éléments du menu.
    function installSmartFiltering(comboInstance) {
        var nativeIsTextExistsAny = comboInstance.isTextExistsAny;
        comboInstance.isTextExistsAny = function (element, query) {
            var haystack = normalize(
                Array.from(element.querySelectorAll("[data-combo-box-search-text]"))
                    .map(function (node) { return node.getAttribute("data-combo-box-search-text") || node.textContent; })
                    .join(" ")
            );
            return matchesSearch(haystack, query);
        };
    }

    // Le moteur stocke ses instances dans cette collection globale : elle doit
    // exister AVANT la première instanciation (le bundle complet la crée via
    // son autoInit, pas le fichier combobox seul).
    window.$hsComboBoxCollection = window.$hsComboBoxCollection || [];

    // Le bundle complet enregistre aussi la fermeture au clic extérieur via
    // son autoInit ; en instanciation directe, c'est à nous de le faire.
    document.addEventListener("click", function (event) {
        if (window.HSComboBox && window.HSComboBox.closeCurrentlyOpened) {
            window.HSComboBox.closeCurrentlyOpened(event.target);
        }
    });

    function buildCombobox(select) {
        if (select.dataset.comboboxReady === "true") {
            return;
        }
        if (!window.HSComboBox) {
            return; // Moteur absent : le <select> natif reste utilisable.
        }
        select.dataset.comboboxReady = "true";

        var wrapper = document.createElement("div");
        wrapper.className = "fx-select";
        wrapper.setAttribute("data-combo-box", "");

        // Champ affiché : sa valeur porte le libellé de l'option choisie,
        // la frappe sert à filtrer la liste (comportement combobox standard).
        var input = document.createElement("input");
        input.type = "text";
        input.setAttribute("data-combo-box-input", "");
        input.className = "fx-select-toggle";
        input.placeholder = select.getAttribute("data-combobox-placeholder") || "Rechercher…";
        input.autocomplete = "off";

        // Chevron, posé par-dessus le bord droit du champ : ouvre la liste.
        var caret = document.createElement("span");
        caret.className = "fx-select-caret";
        caret.setAttribute("data-combo-box-toggle", "");
        caret.setAttribute("aria-hidden", "true");
        caret.textContent = "▾";

        // Menu d'options rendu par HSComboBox à partir des éléments ci-dessous.
        var output = document.createElement("div");
        output.setAttribute("data-combo-box-output", "");
        output.className = "fx-select-menu";

        var itemsWrapper = document.createElement("div");
        itemsWrapper.setAttribute("data-combo-box-output-items-wrapper", "");
        output.appendChild(itemsWrapper);

        wrapper.appendChild(input);
        wrapper.appendChild(caret);
        wrapper.appendChild(output);
        // Masque le select natif seulement maintenant que le composant est
        // en place : sans JS, le select reste visible et le formulaire
        // fonctionne normalement (amélioration progressive).
        select.classList.add("sr-only");
        select.parentNode.insertBefore(wrapper, select);

        var emptyTemplate = (
            '<div class="fx-select-empty" data-combo-box-output-empty>Aucun résultat</div>'
        );

        // Toutes les options sont rendues une fois (y compris hidden/disabled,
        // masquées ou grisées à l'affichage) : les changements ultérieurs ne
        // font plus que basculer des classes, jamais reconstruire la liste.
        var renderedByIndex = [];

        function renderItems() {
            itemsWrapper.innerHTML = "";
            renderedByIndex = [];
            Array.from(select.options).forEach(function (option, index) {
                var label = option.textContent.trim();
                var element = document.createElement("div");
                element.className = "fx-select-option";
                element.setAttribute("data-combo-box-output-item", "");

                var check = document.createElement("span");
                check.className = "fx-select-option-check";
                check.textContent = "✓";

                // Libellé visible ET porteur de l'attribut de recherche : le
                // filtrage du moteur lit l'attribut data-combo-box-search-text.
                var text = document.createElement("span");
                text.setAttribute("data-combo-box-search-text", label);
                text.textContent = label;

                // Valeur canonique en enfant masqué : le moteur lit les
                // descendants [data-combo-box-value] pour trier, comparer la
                // sélection et piloter le clavier — jamais l'élément lui-même.
                var valueHolder = document.createElement("span");
                valueHolder.className = "hidden";
                valueHolder.setAttribute("data-combo-box-value", "");
                valueHolder.setAttribute("data-combo-box-search-text", label);
                valueHolder.textContent = label;

                element.appendChild(check);
                element.appendChild(text);
                element.appendChild(valueHolder);

                if (option.disabled) {
                    element.classList.add("disabled");
                }
                if (option.hidden && !option.selected) {
                    element.style.display = "none";
                }

                // Posé AVANT l'écouteur que HSComboBox ajoutera lui-même :
                // sur un élément, les écouteurs partent dans l'ordre
                // d'enregistrement, donc celui-ci bloque d'abord le clic sur
                // une option désactivée.
                element.addEventListener("click", function (event) {
                    if (option.disabled) {
                        event.stopImmediatePropagation();
                        return;
                    }
                    select.value = option.value;
                    // Le code existant (quiz_setup, formulaires admin…)
                    // écoute l'événement change du select d'origine.
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                });

                renderedByIndex[index] = element;
                itemsWrapper.appendChild(element);
            });
        }

        function syncFromSelect(options) {
            var forceLabel = options && options.forceLabel;
            var selectedOption = select.options[select.selectedIndex];
            var label = selectedOption ? selectedOption.textContent.trim() : "";
            // Pendant une frappe utilisateur (ou une synchro d'état déclenchée
            // par une mutation), ne jamais écraser la recherche en cours ; une
            // assignation programmatique du value, elle, reste autoritaire.
            if (forceLabel || document.activeElement !== input) {
                input.value = label;
            }
            renderedByIndex.forEach(function (element) {
                if (!element) {
                    return;
                }
                var holder = element.querySelector("[data-combo-box-value]");
                element.classList.toggle("selected", holder ? holder.textContent === label : false);
            });
            input.title = label;
        }

        function syncOptionStates() {
            Array.from(select.options).forEach(function (option, index) {
                var element = renderedByIndex[index];
                if (!element) {
                    return;
                }
                element.classList.toggle("disabled", option.disabled);
                element.style.display = (option.hidden && !option.selected) ? "none" : "";
            });
        }

        renderItems();

        // Le moteur lit le contenu du champ au montage : construit AVANT
        // d'écrire le libellé de l'option choisie, sinon il prend ce libellé
        // pour une recherche et masque toutes les autres options.
        var comboInstance = new window.HSComboBox(wrapper, {
            outputEmptyTemplate: emptyTemplate,
            isOpenOnFocus: true,
            keepOriginalOrder: true
        });
        installSmartFiltering(comboInstance);

        // À chaque ouverture, la liste complète revient : le libellé affiché
        // dans le champ n'est jamais un filtre, seule la frappe filtre.
        var originalOpen = comboInstance.open;
        comboInstance.open = function (openValue) {
            this.setResultAndRender("");
            return originalOpen.call(this, openValue);
        };

        syncFromSelect();

        // Suivi de toute mutation externe : disabled/hidden posés par
        // quiz_setup.js (disponibilité), démasquage « Voir tous les univers »…
        var observer = new MutationObserver(function () {
            syncOptionStates();
            syncFromSelect();
        });
        observer.observe(select, { subtree: true, attributes: true, attributeFilter: ["disabled", "hidden", "selected"] });

        // Assignations programmatiques du value (scripts admin) : le
        // comportement natif est préservé, seule la mise à jour visuelle est
        // greffée derrière.
        var valueDescriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
        if (valueDescriptor && valueDescriptor.set) {
            Object.defineProperty(select, "value", {
                get: function () { return valueDescriptor.get.call(select); },
                set: function (newValue) {
                    valueDescriptor.set.call(select, newValue);
                    syncFromSelect({ forceLabel: true });
                }
            });
        }

        select.addEventListener("change", syncFromSelect);

        // Entrée dans le champ de recherche : sert à valider une option, pas
        // à soumettre le formulaire qui contient le select.
        input.addEventListener("keydown", function (event) {
            if (event.key === "Enter" && wrapper.classList.contains("active")) {
                event.preventDefault();
            }
        });

        if (select.disabled) {
            input.disabled = true;
        }
    }

    function mountAll(root) {
        if (!window.HSComboBox) {
            return;
        }
        (root || document).querySelectorAll("select[data-combobox]").forEach(buildCombobox);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { mountAll(); });
    } else {
        mountAll();
    }

    window.FilmatrixCombobox = { mount: mountAll, build: buildCombobox };
})();
