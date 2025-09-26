#!/usr/bin/env python3
"""
Script pour extraire les valeurs FQDN des fichiers YAML/YML dans le dossier apps/
et générer un fichier gatus-config.yml compatible avec Gatus
"""

import os
import yaml
import glob
from pathlib import Path
from datetime import datetime


def find_fqdn_in_yaml(file_path):
    """
    Extrait les valeurs FQDN d'un fichier YAML (supporte les multi-documents)
    """
    fqdns = []
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            # Utiliser yaml.safe_load_all pour gérer les multi-documents
            documents = yaml.safe_load_all(file)
            for doc in documents:
                if doc:  # Ignorer les documents vides
                    fqdns.extend(extract_fqdn_recursive(doc))
    except Exception as e:
        print(f"Erreur lors de la lecture de {file_path}: {e}")

    return fqdns


def extract_fqdn_recursive(obj):
    """
    Recherche récursivement les clés 'fqdn', 'host', 'hosts', et 'domain' dans un objet YAML
    """
    fqdns = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            # Chercher les clés qui contiennent des FQDNs
            if key in ["fqdn", "domain"] and isinstance(value, str):
                # Nettoyer les valeurs qui peuvent contenir des préfixes/suffixes
                clean_value = (
                    value.strip('"')
                    .replace("https://", "")
                    .replace("http://", "")
                    .split("/")[0]
                    .split(":")[0]
                )
                if clean_value.endswith(".club"):
                    fqdns.append(clean_value)
            elif key == "host" and isinstance(value, str):
                # Nettoyer les valeurs host
                clean_value = (
                    value.strip('"')
                    .replace("https://", "")
                    .replace("http://", "")
                    .split("/")[0]
                    .split(":")[0]
                )
                if clean_value.endswith(".club"):
                    fqdns.append(clean_value)
            elif key == "hosts" and isinstance(value, list):
                # Traiter les listes de hosts
                for host_item in value:
                    if isinstance(host_item, str):
                        clean_value = (
                            host_item.strip('"')
                            .replace("https://", "")
                            .replace("http://", "")
                            .split("/")[0]
                            .split(":")[0]
                        )
                        if clean_value.endswith(".club"):
                            fqdns.append(clean_value)
                    elif isinstance(host_item, dict) and "host" in host_item:
                        clean_value = (
                            host_item["host"]
                            .strip('"')
                            .replace("https://", "")
                            .replace("http://", "")
                            .split("/")[0]
                            .split(":")[0]
                        )
                        if clean_value.endswith(".club"):
                            fqdns.append(clean_value)
            else:
                fqdns.extend(extract_fqdn_recursive(value))
    elif isinstance(obj, list):
        for item in obj:
            fqdns.extend(extract_fqdn_recursive(item))

    return fqdns


def create_simple_endpoint(fqdn, app_name, source_file):
    """
    Crée un endpoint simple pour un FQDN donné
    """
    # Créer un nom unique basé sur le FQDN complet
    if "staging" in fqdn:
        endpoint_name = f"{app_name}-staging"
    elif "prod.cedille.club" in fqdn:
        endpoint_name = f"{app_name}-prod"
    else:
        # Utiliser le premier sous-domaine comme identifiant
        subdomain = fqdn.split(".")[0]
        endpoint_name = f"{app_name}-{subdomain}"

    endpoint = {
        "name": endpoint_name,
        "url": f"https://{fqdn}",
        "interval": "5m",
        "conditions": ["[STATUS] == 200", "[RESPONSE_TIME] < 3000"],
    }

    return endpoint


def main():
    """
    Fonction principale
    """
    # Chemin vers le dossier apps
    apps_dir = Path("apps")

    if not apps_dir.exists():
        print("Le dossier 'apps' n'existe pas dans le répertoire courant")
        return

    all_fqdns = []

    # Parcourir récursivement tous les fichiers YAML/YML dans apps/
    yaml_patterns = ["**/*.yaml", "**/*.yml"]

    for pattern in yaml_patterns:
        for yaml_file in apps_dir.glob(pattern):
            print(f"Analyse du fichier: {yaml_file}")
            fqdns = find_fqdn_in_yaml(yaml_file)

            for fqdn in fqdns:
                # Ajouter des métadonnées sur l'origine du FQDN
                endpoint_info = {
                    "fqdn": fqdn,
                    "source_file": str(yaml_file),
                    "app_name": (
                        yaml_file.parts[1] if len(yaml_file.parts) > 1 else "unknown"
                    ),
                }
                all_fqdns.append(endpoint_info)

    # Supprimer les doublons en gardant la première occurrence
    unique_fqdns = []
    seen_fqdns = set()

    for endpoint in all_fqdns:
        if endpoint["fqdn"] not in seen_fqdns:
            unique_fqdns.append(endpoint)
            seen_fqdns.add(endpoint["fqdn"])

    # Trier par nom d'application puis par FQDN
    unique_fqdns.sort(key=lambda x: (x["app_name"], x["fqdn"]))

    # Créer la liste des endpoints
    endpoints_list = []
    for endpoint_info in unique_fqdns:
        endpoint = create_simple_endpoint(
            endpoint_info["fqdn"],
            endpoint_info["app_name"],
            endpoint_info["source_file"],
        )
        endpoints_list.append(endpoint)

    # Structure simple avec juste les endpoints
    endpoints_config = {
        "# Configuration générée automatiquement": f"Généré le {datetime.now().isoformat()}",
        "endpoints": endpoints_list,
    }

    # Écrire le fichier gatus-endpoints.yml
    with open("gatus-endpoints.yml", "w", encoding="utf-8") as f:
        yaml.dump(
            endpoints_config,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    print(
        f"Fichier gatus-endpoints.yml généré avec {len(unique_fqdns)} endpoints uniques"
    )

    # Afficher un résumé
    print("\nEndpoints trouvés:")
    for endpoint in unique_fqdns:
        print(f"  - {endpoint['fqdn']} (app: {endpoint['app_name']})")

    print(f"\nFichier généré:")
    print(f"  - gatus-endpoints.yml (endpoints pour Gatus)")


if __name__ == "__main__":
    main()
