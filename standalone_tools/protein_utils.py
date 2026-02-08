"""Protein Utilities - MW Lookup and Concentration Conversion.

Standalone testing utility for SPR concentration calculations.
Connects to UniProt API for molecular weight lookup.

Usage Examples:
    # Look up protein MW from UniProt
    python protein_utils.py --uniprot P01375
    
    # Convert concentration with known MW
    python protein_utils.py --convert 100 --from-unit nM --to-unit ug/mL --mw 150000
    
    # Interactive mode
    python protein_utils.py --interactive
"""

import argparse
import sys
from typing import Optional, Dict
import requests
from pint import UnitRegistry

# Initialize unit registry
ureg = UnitRegistry()
Q_ = ureg.Quantity


class ProteinUtility:
    """Utility for protein MW lookup and concentration conversions."""
    
    UNIPROT_API = "https://rest.uniprot.org/uniprotkb"
    
    def __init__(self):
        """Initialize the protein utility."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AffiLabs-SPR/1.0 (contact@affilabs.com)'
        })
    
    def fetch_uniprot_data(self, uniprot_id: str) -> Optional[Dict]:
        """Fetch protein data from UniProt by accession ID.
        
        Args:
            uniprot_id: UniProt accession (e.g., 'P01375' for TNF-alpha)
            
        Returns:
            Dictionary with protein data or None if not found
        """
        try:
            # Clean up the ID - remove whitespace and convert to uppercase
            uniprot_id = uniprot_id.strip().upper()
            
            url = f"{self.UNIPROT_API}/{uniprot_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                parsed = self._parse_uniprot_response(data)
                # Add uniprot_id and mw_kda for compatibility
                if parsed:
                    parsed['uniprot_id'] = uniprot_id
                    if parsed.get('mw_da'):
                        parsed['mw_kda'] = parsed['mw_da'] / 1000.0
                    else:
                        parsed['mw_kda'] = 0.0
                return parsed
            elif response.status_code == 404:
                print(f"❌ UniProt ID '{uniprot_id}' not found")
                return None
            else:
                print(f"❌ UniProt API error: {response.status_code}")
                print(f"URL: {url}")
                print(f"Response: {response.text[:200]}")
                return None
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            return None
    
    def _parse_uniprot_response(self, data: Dict) -> Dict:
        """Parse UniProt JSON response.
        
        Args:
            data: Raw JSON response from UniProt
            
        Returns:
            Simplified dictionary with useful fields
        """
        result = {
            'accession': data.get('primaryAccession', 'Unknown'),
            'name': 'Unknown',
            'organism': 'Unknown',
            'mw_da': None,
            'sequence_length': 0,
            'sequence': None
        }
        
        # Extract protein name
        if 'proteinDescription' in data:
            rec_name = data['proteinDescription'].get('recommendedName', {})
            result['name'] = rec_name.get('fullName', {}).get('value', 'Unknown')
        
        # Extract organism
        if 'organism' in data:
            result['organism'] = data['organism'].get('scientificName', 'Unknown')
        
        # Extract sequence and calculate MW
        if 'sequence' in data:
            seq_data = data['sequence']
            result['sequence'] = seq_data.get('value', '')
            result['sequence_length'] = seq_data.get('length', 0)
            result['mw_da'] = seq_data.get('molWeight', None)  # in Daltons
        
        return result
    
    def search_uniprot_by_name(self, protein_name: str, organism: str = "human", limit: int = 10) -> Optional[list]:
        """Search UniProt by protein name.
        
        Args:
            protein_name: Protein name to search
            organism: Organism filter (default: human)
            limit: Maximum number of results to return (default: 10)
            
        Returns:
            List of matching entries with ID and name
        """
        try:
            query = f"(protein_name:{protein_name}) AND (organism_name:{organism})"
            url = f"{self.UNIPROT_API}/search"
            params = {
                'query': query,
                'format': 'json',
                'size': limit
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for entry in data.get('results', []):
                    acc = entry.get('primaryAccession', 'Unknown')
                    name = 'Unknown'
                    
                    if 'proteinDescription' in entry:
                        rec_name = entry['proteinDescription'].get('recommendedName', {})
                        name = rec_name.get('fullName', {}).get('value', 'Unknown')
                    
                    mw = None
                    if 'sequence' in entry:
                        mw = entry['sequence'].get('molWeight', None)
                    
                    results.append({
                        'accession': acc,
                        'name': name,
                        'mw_da': mw
                    })
                
                return results
            else:
                print(f"❌ Search failed: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            return None
    
    def convert_concentration(
        self,
        value: float,
        from_unit: str,
        to_unit: str,
        mw_da: float
    ) -> Optional[float]:
        """Convert between mass and molar concentrations.
        
        Args:
            value: Concentration value
            from_unit: Source unit (nM, uM, mM, M, ug/mL, mg/mL, ng/mL)
            to_unit: Target unit
            mw_da: Molecular weight in Daltons
            
        Returns:
            Converted concentration value
        """
        try:
            # Map common units to Pint-compatible strings
            unit_map = {
                'nM': 'nanomolar',
                'uM': 'micromolar',
                'µM': 'micromolar',
                'mM': 'millimolar',
                'M': 'molar',
                'pM': 'picomolar',
                'ug/mL': 'microgram / milliliter',
                'µg/mL': 'microgram / milliliter',
                'mg/mL': 'milligram / milliliter',
                'ng/mL': 'nanogram / milliliter',
                'g/L': 'gram / liter'
            }
            
            from_pint = unit_map.get(from_unit, from_unit)
            to_pint = unit_map.get(to_unit, to_unit)
            
            # Create quantity with source unit
            quantity = Q_(value, from_pint)
            
            # Check if conversion requires MW (molar <-> mass)
            from_is_molar = 'molar' in from_pint.lower() or from_pint == 'M'
            to_is_molar = 'molar' in to_pint.lower() or to_pint == 'M'
            
            if from_is_molar and not to_is_molar:
                # Molar -> Mass: multiply by MW
                # nM -> ug/mL: (nM * MW_Da) / 1000
                # Example: 100 nM of 150 kDa protein = (100e-9 M * 150000 g/mol) = 15e-6 g/L = 15 ug/mL
                molar_conc = quantity.to('molar').magnitude  # Convert to molar first
                mass_conc_g_per_L = molar_conc * mw_da  # g/L
                result = Q_(mass_conc_g_per_L, 'gram / liter').to(to_pint)
                return result.magnitude
                
            elif not from_is_molar and to_is_molar:
                # Mass -> Molar: divide by MW
                # ug/mL -> nM: (ug/mL * 1000) / MW_Da
                mass_g_per_L = quantity.to('gram / liter').magnitude
                molar_conc = mass_g_per_L / mw_da  # mol/L
                result = Q_(molar_conc, 'molar').to(to_pint)
                return result.magnitude
                
            else:
                # Same type (molar-to-molar or mass-to-mass)
                result = quantity.to(to_pint)
                return result.magnitude
                
        except Exception as e:
            print(f"❌ Conversion error: {e}")
            return None
    
    def print_protein_info(self, data: Dict):
        """Pretty print protein information.
        
        Args:
            data: Protein data dictionary
        """
        print("\n" + "="*70)
        print("PROTEIN INFORMATION")
        print("="*70)
        print(f"UniProt ID:    {data['accession']}")
        print(f"Name:          {data['name']}")
        print(f"Organism:      {data['organism']}")
        print(f"Length:        {data['sequence_length']} amino acids")
        
        if data['mw_da']:
            mw_kda = data['mw_da'] / 1000
            print(f"Molecular Weight: {data['mw_da']:.2f} Da ({mw_kda:.2f} kDa)")
        else:
            print("Molecular Weight: Not available")
        
        print("="*70 + "\n")


def interactive_mode():
    """Run interactive mode for protein utilities."""
    util = ProteinUtility()
    
    print("\n" + "="*70)
    print("PROTEIN UTILITY - INTERACTIVE MODE")
    print("="*70)
    print("\nOptions:")
    print("  1) Look up protein by UniProt ID")
    print("  2) Search protein by name")
    print("  3) Convert concentration")
    print("  4) Exit")
    print("="*70)
    
    while True:
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == '1':
            uniprot_id = input("Enter UniProt ID (e.g., P01375): ").strip()
            data = util.fetch_uniprot_data(uniprot_id)
            if data:
                util.print_protein_info(data)
                
                # Offer conversion
                do_convert = input("\nConvert concentration? (y/n): ").strip().lower()
                if do_convert == 'y' and data['mw_da']:
                    try:
                        value = float(input("  Enter value: "))
                        from_unit = input("  From unit (nM, µM, µg/mL, etc.): ").strip()
                        to_unit = input("  To unit: ").strip()
                        
                        result = util.convert_concentration(value, from_unit, to_unit, data['mw_da'])
                        if result is not None:
                            print(f"\n  ✓ {value} {from_unit} = {result:.6g} {to_unit}")
                    except ValueError:
                        print("  ❌ Invalid number")
        
        elif choice == '2':
            protein_name = input("Enter protein name (e.g., TNF): ").strip()
            organism = input("Organism (default: human): ").strip() or "human"
            
            results = util.search_uniprot_by_name(protein_name, organism)
            if results:
                print(f"\n Found {len(results)} results:\n")
                for i, entry in enumerate(results, 1):
                    mw_str = f"{entry['mw_da']/1000:.1f} kDa" if entry['mw_da'] else "N/A"
                    print(f"  {i}. {entry['accession']} - {entry['name']} ({mw_str})")
        
        elif choice == '3':
            try:
                value = float(input("Enter concentration value: "))
                from_unit = input("From unit (nM, µM, µg/mL, etc.): ").strip()
                to_unit = input("To unit: ").strip()
                mw_da = float(input("Molecular weight (Da): "))
                
                result = util.convert_concentration(value, from_unit, to_unit, mw_da)
                if result is not None:
                    print(f"\n  ✓ {value} {from_unit} = {result:.6g} {to_unit}")
            except ValueError:
                print("  ❌ Invalid input")
        
        elif choice == '4':
            print("\nExiting...")
            break
        
        else:
            print("❌ Invalid option")


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Protein MW Lookup and Concentration Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Look up protein by UniProt ID
  python protein_utils.py --uniprot P01375
  
  # Search by name
  python protein_utils.py --search "TNF alpha" --organism human
  
  # Convert concentration (requires MW)
  python protein_utils.py --convert 100 --from-unit nM --to-unit ug/mL --mw 150000
  
  # Interactive mode
  python protein_utils.py --interactive
        """
    )
    
    parser.add_argument('--uniprot', help='UniProt accession ID')
    parser.add_argument('--search', help='Search protein by name')
    parser.add_argument('--organism', default='human', help='Organism for search (default: human)')
    parser.add_argument('--convert', type=float, help='Concentration value to convert')
    parser.add_argument('--from-unit', help='Source unit (nM, µM, µg/mL, etc.)')
    parser.add_argument('--to-unit', help='Target unit')
    parser.add_argument('--mw', type=float, help='Molecular weight in Daltons')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    
    args = parser.parse_args()
    
    util = ProteinUtility()
    
    # Interactive mode
    if args.interactive:
        interactive_mode()
        return
    
    # UniProt lookup
    if args.uniprot:
        data = util.fetch_uniprot_data(args.uniprot)
        if data:
            util.print_protein_info(data)
    
    # Search by name
    elif args.search:
        results = util.search_uniprot_by_name(args.search, args.organism)
        if results:
            print(f"\n Found {len(results)} results:\n")
            for i, entry in enumerate(results, 1):
                mw_str = f"{entry['mw_da']/1000:.1f} kDa" if entry['mw_da'] else "N/A"
                print(f"  {i}. {entry['accession']} - {entry['name']} ({mw_str})")
    
    # Concentration conversion
    elif args.convert is not None:
        if not all([args.from_unit, args.to_unit, args.mw]):
            print("❌ Conversion requires --from-unit, --to-unit, and --mw")
            sys.exit(1)
        
        result = util.convert_concentration(
            args.convert,
            args.from_unit,
            args.to_unit,
            args.mw
        )
        
        if result is not None:
            print(f"\n✓ {args.convert} {args.from_unit} = {result:.6g} {args.to_unit}\n")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
