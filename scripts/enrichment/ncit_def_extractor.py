#!/usr/bin/env python3
"""
NCIT Definition Extractor

This script migrates RDF ontology files by:
1. Extracting NCIT IDs from rdfs:seeAlso properties
2. Splitting rdfs:comment into name (synonym) and definition
3. Converting them to proper OWL axioms with NCIT cross-references
4. Cleaning up the original properties

Usage:
    python ncit_def_extractor.py <source_file> <destination_file>

Example:
    python ncit_def_extractor.py _hpvco.rdf hpvco.rdf
"""

from rdflib import Graph, Namespace, URIRef, BNode, Literal
from rdflib.namespace import RDF, RDFS, OWL
import argparse
import pathlib
import sys

# Define namespaces
OIO = Namespace("http://www.geneontology.org/formats/oboInOwl#")
IAO_DEF = URIRef("http://purl.obolibrary.org/obo/IAO_0000115")
HAS_SYN = OIO.hasSynonym
HAS_XREF = OIO.hasDbXref


def graft_axiom(g: Graph, subj: URIRef, prop: URIRef,
                tgt_literal: Literal, xref_literal: Literal):
    """
    Add:
        subj  prop  tgt_literal .
    and:
        [ rdf:type         owl:Axiom ;
          owl:annotatedSource    subj ;
          owl:annotatedProperty  prop ;
          owl:annotatedTarget    tgt_literal ;
          oio:hasDbXref          xref_literal ] .
    """
    # assertion triple
    g.add((subj, prop, tgt_literal))

    # reified axiom
    ax = BNode()
    g.add((ax, RDF.type, OWL.Axiom))  # add axiom node
    g.add((ax, OWL.annotatedSource, subj))
    g.add((ax, OWL.annotatedProperty, prop))
    g.add((ax, OWL.annotatedTarget, tgt_literal))
    g.add((ax, HAS_XREF, xref_literal))


def migrate(in_path: pathlib.Path, out_path: pathlib.Path):
    """
    Main conversion routine that processes the RDF file.
    
    Args:
        in_path: Path to the input RDF file
        out_path: Path to the output RDF file
    """
    g = Graph()
    
    try:
        g.parse(in_path)  # auto-detect format
        print(f"✔  Loaded ontology from {in_path}")
    except Exception as e:
        print(f"✗  Error loading {in_path}: {e}")
        sys.exit(1)

    processed_count = 0
    
    for cls in g.subjects(RDFS.seeAlso, None):
        # ---- 1) NCIT ID -----------------------------------------------------
        ncit_raw = str(next(g.objects(cls, RDFS.seeAlso)))
        ncit_id = ncit_raw if ncit_raw.startswith("NCIT:") else f"NCIT:{ncit_raw}"
        xref_lit = Literal(ncit_id)

        # ---- 2) Split comments into name vs definition ----------------------
        coms = list(g.objects(cls, RDFS.comment))
        if len(coms) < 2:
            continue  # skip if we don't have both pieces
        coms_sorted = sorted(coms, key=lambda lit: len(str(lit)))
        name_lit, def_lit = coms_sorted[0], coms_sorted[-1]  # since definition is usually longer than name

        # ---- 3) Add new annotations wrapped in owl:Axiom --------------------
        graft_axiom(g, cls, IAO_DEF, def_lit, xref_lit)
        graft_axiom(g, cls, HAS_SYN, name_lit, xref_lit)

        # ---- 4) (optional) cleanup ------------------------------------------
        g.remove((cls, RDFS.comment, name_lit))
        g.remove((cls, RDFS.comment, def_lit))
        g.remove((cls, RDFS.seeAlso, Literal(ncit_raw)))
        
        processed_count += 1

    try:
        g.serialize(out_path, format="xml")  # default RDF/XML
        print(f"✔  Processed {processed_count} classes")
        print(f"✔  Saved enriched ontology to {out_path}")
    except Exception as e:
        print(f"✗  Error saving to {out_path}: {e}")
        sys.exit(1)


def main():
    """Main function that handles command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract NCIT definitions and convert RDF ontology format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ncit_def_extractor.py _hpvco.rdf hpvco.rdf
  python ncit_def_extractor.py input.owl output.rdf
        """
    )
    
    parser.add_argument(
        "source_file",
        type=str,
        help="Path to the source RDF/OWL file"
    )
    
    parser.add_argument(
        "destination_file", 
        type=str,
        help="Path to the destination RDF file"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()
    
    # Convert string paths to Path objects
    src_path = pathlib.Path(args.source_file)
    dst_path = pathlib.Path(args.destination_file)
    
    # Validate input file exists
    if not src_path.exists():
        print(f"✗  Error: Source file '{src_path}' does not exist")
        sys.exit(1)
    
    if not src_path.is_file():
        print(f"✗  Error: '{src_path}' is not a file")
        sys.exit(1)
    
    # Ensure output directory exists
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    
    if args.verbose:
        print(f"Source file: {src_path}")
        print(f"Destination file: {dst_path}")
    
    # Run the migration
    migrate(src_path, dst_path)


if __name__ == "__main__":
    main()
