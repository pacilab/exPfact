"""
MD2Pfact

Calculated protection factors from a Molecular Dynamics trajectory (.dcd file)
using the Best-Vendruscolo model:
    
    < ln(P) > = beta_c * < N_c > + beta_h * < N_h >

where N_c is the number of heavy contacts and N_h the number of hydrogen bonds.
 
Usage:
    python MD2Pfact.py --pdb input.pdb --dcd input.dcd --out output_folder 
                      [--bc beta_c --bh beta_h --step step]
    
Parameters:
    --pdb       input structure file (pdb format)
    --dcd       input trajectory file (dcd format)
    --out       common name of the output files

[optional]
    --bc        constant for heavy contacts (default: 0.35)
    --bh        constant for hydrogen bonds (default: 2.00)
    --step      integer, protection factors are calculated every <step>
                    frame of the simulation (default: 100). 
"""

import argparse
import MDAnalysis
import MDAnalysis.analysis.distances
import numpy as np
import matplotlib.pyplot as plt
import time 
import Bio.SeqUtils
import os 

def contacts_smooth_function(dist):
	den = 1 + np.exp( 5 * (dist - 6.5))
	return 1 / den

def hydrogen_bonds_smooth_function(dist):
	den = 1 + np.exp(10 * (dist - 2.4))
	return 1 / den

def evaluate_pfact(Nc, Nh, A = 0.35, B = 2.00):
	pfact = A * Nc + B * Nh 
	return pfact

def calculate_pfact_from_trajectory(PDB, DCD, OUT, step = 100, bh = 2.00, bc = 0.35):
    
    u = MDAnalysis.Universe(PDB, DCD)

    segids = list(u.select_atoms("protein").segids)
    chains = []
    for segid in segids:
        if segid not in chains:
            chains.append(segid)
    
    if (len(chains) == 1):
        monomer = True
    else:
        monomer = False
    
    number_of_frames = len(u.trajectory)
    residues = np.sort(list((set(u.select_atoms("protein").residues.resnums))))
    sequence = u.select_atoms("protein").residues.resnames
    
    seq = ""
    for x in sequence:
        if x == 'HSD':
            x = 'His'
        seq += Bio.SeqUtils.IUPACData.protein_letters_3to1[x.capitalize()]
    with open(PDB.replace(".pdb", ".seq"), 'w') as f:
        f.write("%s" % seq)
    
    pfact = []
    for ts in u.trajectory[0:number_of_frames:step]:
        pfact_t = []
        for chain in chains:
            for r in residues:
                amide_nitrogen = u.select_atoms("protein and segid %s and name N and resid %s" % (chain, r))
            
                #exclude_neighbours = u.select_atoms("not resid %s and not resid %s and not resid %s" % (r, r-1, r+1))
                exclude_neighbours = u.select_atoms("not resid %s and not resid %s and not resid %s and not resid %s and not resid %s" % (r, r-1, r+1, r-2, r+2))
    
                O_list = exclude_neighbours.select_atoms("type O")
                H_list = exclude_neighbours.select_atoms("not type H")
                
                dist_O = MDAnalysis.analysis.distances.distance_array(amide_nitrogen, O_list)[0]
                dist_H = MDAnalysis.analysis.distances.distance_array(amide_nitrogen, H_list)[0]
                
                Nc = np.sum(contacts_smooth_function(dist_H))
                Nh = np.sum(hydrogen_bonds_smooth_function(dist_O))
                
                p = evaluate_pfact(Nc, Nh, bc, bh)
                pfact_t.append(p)
        pfact.append(pfact_t)
        
    p_all = np.array(pfact)
    p_avg = np.mean(p_all, axis = 0)
    p_std = np.std(p_all, axis = 0)
    
    np.savetxt("%s_all.txt" % OUT, p_all, fmt = '%.5e')
    
    if monomer == False:
        residues = list(residues) * len(chains)
        residues = [i for i in range(len(residues))]

    with open("%s_avg.txt" % OUT, 'w') as f:
        for i in range(len(residues)):
            f.write("%d %.5e %.5e\n" % (residues[i]+1, p_avg[i], p_std[i]))
        
    return residues, p_avg, p_std, p_all


if __name__ == '__main__':

    os.system("conda activate base")
    parser = argparse.ArgumentParser()

    parser.add_argument("--pdb")
    parser.add_argument("--dcd")
    parser.add_argument("--out")

    parser.add_argument("--step")
    parser.add_argument("--bh")
    parser.add_argument("--bc")

    config = {}
    opts = parser.parse_args()

    # Compulsory arguments
    if opts.pdb:
        config['pdb'] = opts.pdb
    if opts.dcd:
        config['dcd'] = opts.dcd
    if opts.out:
        config['out'] = opts.out
    if opts.step:
        config['step'] = int(opts.step)
    else:
        config['step'] = 100
    if opts.bc:
        config['bc'] = float(opts.bc)
    else:
        config['bc'] = 0.35
    if opts.bh:
        config['bh'] = float(opts.bh)
    else:
        config['bh'] = 2.00
    

    #try: 
    PDB = config['pdb']
    DCD = config['dcd']
    OUT = config['out']
    step = config['step']
    bh = config['bh']
    bc = config['bc']
    
    start = time.time()
    residues, p_avg, p_std, p_all = calculate_pfact_from_trajectory(PDB, DCD, OUT, step, bh, bc)
    end = time.time()
    dt = end - start
    print("Elapsed time: %5.5f s" % dt)
    
    plt.figure()
    plt.title("Protection Factors from %s" % DCD, fontsize = 15)
    plt.errorbar(residues, p_avg, p_std, fmt = 'o-', color = 'black', capsize = 2)
    plt.xlabel("Residue Index", fontsize = 15)
    plt.ylabel("<ln(P)>", fontsize = 15)
    plt.ylim(-1, 21)
    plt.savefig("%s_avg.png" % OUT, dpi = 300)
    plt.show()
    
    #except:
    #    print(__doc__)
