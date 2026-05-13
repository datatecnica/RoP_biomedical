#!/usr/bin/env python3
"""
Create RoP v2026.04 Summary Figure
Shows: deduplication (1.39M→1.33M), 13 themes, FAISS clustering, and impact
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# Set up the figure with a clean, professional style
plt.style.use('seaborn-v0_8-darkgrid')
fig = plt.figure(figsize=(16, 10))
fig.patch.set_facecolor('white')

# Create layout: 3 main sections
gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1.5, 1], hspace=0.35, wspace=0.3)

# ==============================================================================
# TOP: Harmonization Pipeline (1.39M → 1.33M)
# ==============================================================================
ax_pipeline = fig.add_subplot(gs[0, :])
ax_pipeline.set_xlim(0, 10)
ax_pipeline.set_ylim(0, 2)
ax_pipeline.axis('off')

# Input sources
input_box = FancyBboxPatch((0.3, 0.7), 1.4, 1.0,
                           boxstyle="round,pad=0.1",
                           edgecolor='#2E86AB', facecolor='#A23B72',
                           linewidth=3, alpha=0.8)
ax_pipeline.add_patch(input_box)
ax_pipeline.text(1.0, 1.35, '9 Public Standards',
                ha='center', va='center', fontsize=13, fontweight='bold', color='white')
ax_pipeline.text(1.0, 0.95, 'OMOP • LOINC • ICD-10\nHPO • Mondo • NINDS-CDE\nPhenX • CDISC • DICOM',
                ha='center', va='center', fontsize=8, color='white')

# Arrow to dedup
arrow1 = FancyArrowPatch((1.8, 1.2), (2.6, 1.2),
                        arrowstyle='->', mutation_scale=30,
                        linewidth=3, color='#2E86AB')
ax_pipeline.add_patch(arrow1)
ax_pipeline.text(2.2, 1.55, 'Harvest\nXrefs', ha='center', va='center',
                fontsize=9, fontweight='bold', color='#2E86AB')

# Deduplication
dedup_box = FancyBboxPatch((2.7, 0.7), 1.4, 1.0,
                          boxstyle="round,pad=0.1",
                          edgecolor='#2E86AB', facecolor='#F18F01',
                          linewidth=3, alpha=0.8)
ax_pipeline.add_patch(dedup_box)
ax_pipeline.text(3.4, 1.4, 'Deduplication',
                ha='center', va='center', fontsize=13, fontweight='bold', color='white')
ax_pipeline.text(3.4, 1.1, '1.39M → 1.33M',
                ha='center', va='center', fontsize=11, fontweight='bold', color='white')
ax_pipeline.text(3.4, 0.85, '88K equivalences',
                ha='center', va='center', fontsize=8, color='white')

# Arrow to embeddings
arrow2 = FancyArrowPatch((4.2, 1.2), (5.0, 1.2),
                        arrowstyle='->', mutation_scale=30,
                        linewidth=3, color='#2E86AB')
ax_pipeline.add_patch(arrow2)
ax_pipeline.text(4.6, 1.55, 'SapBERT\nEmbedding', ha='center', va='center',
                fontsize=9, fontweight='bold', color='#2E86AB')

# Embeddings + FAISS
output_box = FancyBboxPatch((5.1, 0.7), 1.8, 1.0,
                           boxstyle="round,pad=0.1",
                           edgecolor='#2E86AB', facecolor='#6A994E',
                           linewidth=3, alpha=0.8)
ax_pipeline.add_patch(output_box)
ax_pipeline.text(6.0, 1.4, '1.33M CDEs',
                ha='center', va='center', fontsize=13, fontweight='bold', color='white')
ax_pipeline.text(6.0, 1.1, '768-dim embeddings',
                ha='center', va='center', fontsize=9, color='white')
ax_pipeline.text(6.0, 0.85, 'IVF4096 FAISS index',
                ha='center', va='center', fontsize=9, color='white')

# Arrow to impact
arrow3 = FancyArrowPatch((7.0, 1.2), (7.8, 1.2),
                        arrowstyle='->', mutation_scale=30,
                        linewidth=3, color='#2E86AB')
ax_pipeline.add_patch(arrow3)

# Impact box
impact_box = FancyBboxPatch((7.9, 0.5), 1.8, 1.3,
                           boxstyle="round,pad=0.1",
                           edgecolor='#2E86AB', facecolor='#BC4B51',
                           linewidth=3, alpha=0.8)
ax_pipeline.add_patch(impact_box)
ax_pipeline.text(8.8, 1.55, 'Impact',
                ha='center', va='center', fontsize=13, fontweight='bold', color='white')
ax_pipeline.text(8.8, 1.25, '<1 sec',
                ha='center', va='center', fontsize=11, fontweight='bold', color='white')
ax_pipeline.text(8.8, 1.05, 'similarity search',
                ha='center', va='center', fontsize=8, color='white')
ax_pipeline.text(8.8, 0.75, '40-70%',
                ha='center', va='center', fontsize=11, fontweight='bold', color='white')
ax_pipeline.text(8.8, 0.58, 'time saved',
                ha='center', va='center', fontsize=8, color='white')

# Title
ax_pipeline.text(5.0, 1.9, 'RoP v2026.04 Harmonization Pipeline',
                ha='center', va='center', fontsize=18, fontweight='bold', color='#2E86AB')

# ==============================================================================
# MIDDLE LEFT: 13 Themes
# ==============================================================================
ax_themes = fig.add_subplot(gs[1, 0])
ax_themes.set_xlim(0, 10)
ax_themes.set_ylim(0, 15.5)
ax_themes.axis('off')

themes = [
    ('1', 'Identity', '#E63946'),
    ('2', 'Time', '#F77F00'),
    ('3', 'Sex', '#FCBF49'),
    ('4', 'Ancestry & Pedigree', '#EAE2B7'),
    ('5', 'Biosample', '#8AC926'),
    ('6', 'Omics Platform', '#52B788'),
    ('7', 'Imaging Acquisition', '#1A759F'),
    ('8', 'Clinical Assessment Instruments', '#184E77'),
    ('9', 'Governance & Consent', '#6A4C93'),
    ('10', 'Data Asset References', '#9D4EDD'),
    ('11', 'Summary Statistics', '#C77DFF'),
    ('12', 'Clinical Concepts', '#E0AAFF'),
    ('13a', 'Discoverability — Resources', '#F72585'),
    ('13b', 'Discoverability — Collections', '#C9184A'),
]

y_start = 14
for i, (num, name, color) in enumerate(themes):
    y_pos = y_start - i * 0.95

    # Theme box
    box = FancyBboxPatch((0.5, y_pos - 0.4), 9, 0.85,
                        boxstyle="round,pad=0.05",
                        edgecolor=color, facecolor=color,
                        linewidth=2, alpha=0.7)
    ax_themes.add_patch(box)

    # Theme number and name
    ax_themes.text(1.0, y_pos, f'Theme {num}',
                  ha='left', va='center', fontsize=10, fontweight='bold', color='white')
    ax_themes.text(3.5, y_pos, name,
                  ha='left', va='center', fontsize=10, color='white')

# Title
ax_themes.text(5.0, 15.2, '13 Themes: Complete Biomedical Coverage',
              ha='center', va='center', fontsize=16, fontweight='bold', color='#2E86AB')

# ==============================================================================
# MIDDLE RIGHT: FAISS IVF4096 Clustering
# ==============================================================================
ax_faiss = fig.add_subplot(gs[1, 1])
ax_faiss.set_xlim(0, 10)
ax_faiss.set_ylim(0, 10)
ax_faiss.axis('off')

# Draw cluster visualization
np.random.seed(42)
n_clusters_shown = 12  # Show subset of 4096
cluster_positions = np.random.rand(n_clusters_shown, 2) * 8 + 1

for i, (x, y) in enumerate(cluster_positions):
    # Cluster circle
    circle = plt.Circle((x, y), 0.4, color='#2E86AB', alpha=0.6, ec='#184E77', linewidth=2)
    ax_faiss.add_patch(circle)

    # Cluster label
    ax_faiss.text(x, y, f'C{i+1}', ha='center', va='center',
                 fontsize=8, fontweight='bold', color='white')

    # Show some points in cluster
    n_points = np.random.randint(3, 8)
    angles = np.linspace(0, 2*np.pi, n_points, endpoint=False)
    for angle in angles:
        px = x + 0.25 * np.cos(angle)
        py = y + 0.25 * np.sin(angle)
        ax_faiss.plot(px, py, 'o', color='#F18F01', markersize=3, alpha=0.7)

# Info box
info_box = FancyBboxPatch((0.5, 8.5), 9, 1.2,
                         boxstyle="round,pad=0.1",
                         edgecolor='#2E86AB', facecolor='#6A994E',
                         linewidth=2, alpha=0.3)
ax_faiss.add_patch(info_box)
ax_faiss.text(5.0, 9.3, 'IVF4096: Inverted File Index with 4,096 Clusters',
             ha='center', va='center', fontsize=12, fontweight='bold', color='#184E77')
ax_faiss.text(5.0, 8.8, 'Sub-second semantic search across 1.33M elements',
             ha='center', va='center', fontsize=10, color='#184E77')

# Title
ax_faiss.text(5.0, 10.5, 'FAISS Clustering Architecture',
             ha='center', va='center', fontsize=16, fontweight='bold', color='#2E86AB')

# Note
ax_faiss.text(5.0, 0.5, '(Showing 12 of 4,096 clusters)',
             ha='center', va='center', fontsize=9, style='italic', color='#666')

# ==============================================================================
# BOTTOM: Why It Matters
# ==============================================================================
ax_why = fig.add_subplot(gs[2, :])
ax_why.set_xlim(0, 10)
ax_why.set_ylim(0, 3)
ax_why.axis('off')

# Three impact boxes
impact_data = [
    ('Interoperability',
     'One RoP ID → instant\ncompatibility across\nfederated studies',
     '#E63946', 1.5),
    ('AI-Ready',
     'Semantic embeddings enable\nAI-assisted harmonization\n(10x faster)',
     '#F18F01', 5.0),
    ('FAIR',
     'Findable, Accessible,\nInteroperable, Reusable\nby design',
     '#6A994E', 8.5),
]

for title, text, color, x_pos in impact_data:
    box = FancyBboxPatch((x_pos - 1.2, 0.3), 2.4, 2.0,
                        boxstyle="round,pad=0.1",
                        edgecolor=color, facecolor=color,
                        linewidth=3, alpha=0.7)
    ax_why.add_patch(box)

    ax_why.text(x_pos, 2.0, title,
               ha='center', va='center', fontsize=14, fontweight='bold', color='white')
    ax_why.text(x_pos, 1.2, text,
               ha='center', va='center', fontsize=10, color='white')

# Title
ax_why.text(5.0, 2.8, 'Why RoP Matters: Decreasing Activation Energy in Biomedical Research',
           ha='center', va='center', fontsize=16, fontweight='bold', color='#2E86AB')

# Footer
fig.text(0.5, 0.02, 'RoP v2026.04 | DataTecnica | doi:10.57967/hf/8781 | AGPLv3 + CC-BY-NC-4.0',
         ha='center', fontsize=10, color='#666')

# Save
output_path = '/mnt/c/USers/mike1/Projects/RoP_build_kit/rop_build/docs/rop_v2026.04_summary.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"✅ Saved summary figure to: {output_path}")

# Also save high-res version
output_path_highres = '/mnt/c/USers/mike1/Projects/RoP_build_kit/rop_build/docs/rop_v2026.04_summary_highres.png'
plt.savefig(output_path_highres, dpi=600, bbox_inches='tight', facecolor='white')
print(f"✅ Saved high-res version to: {output_path_highres}")

plt.close()
