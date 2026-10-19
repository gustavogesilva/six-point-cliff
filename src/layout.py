NUM = '#,##0.0;(#,##0.0);"-"'; NUM2 = '#,##0.00;(#,##0.00);"-"'; PCT = '0.0%;(0.0%);"-"'; PCT2 = '0.00%;(0.00%);"-"'; INT = '0;(0);"-"'
FIELDS = [  # key, header, fmt, kind ('in' or formula template using {r})
 ('id', 'Id', None, 'in'), ('name', 'Institution', None, 'in'), ('ccy', 'Report ccy', None, 'in'), ('gsib', 'G-SIB (1/0)', INT, 'in'),
 ('aoci', 'AFS/OCI in CET1 (1/0)', INT, 'in'), ('n_hy', 'Notches to HY', INT, 'in'),
 ('cet1', 'CET1 ($bn)', NUM, 'in'), ('rwa', 'RWA ($bn)', NUM, 'in'), ('req', 'CET1 req. incl. buffers (MDA)', PCT2, 'in'),
 ('ppnr_q', 'PPNR / quarter ($bn)', NUM, 'in'), ('afs_fv', 'AFS / FVOCI debt FV ($bn)', NUM, 'in'), ('afs_ul', 'AFS unrealised loss ($bn)', NUM, 'in'),
 ('htm_ac', 'HTM / AC book ($bn)', NUM, 'in'), ('htm_ul', 'HTM unrealised loss ($bn)', NUM, 'in'), ('dur_afs', 'AFS net duration (yrs)', NUM2, 'in'),
 ('strat_eq', 'Strategic equities ($bn)', NUM, 'in'),
 ('bl_d', 'Back-leverage drawn ($bn)', NUM, 'in'), ('bl_u', 'Back-leverage undrawn ($bn)', NUM, 'in'),
 ('ff_d', 'Fund finance drawn ($bn)', NUM, 'in'), ('ff_u', 'Fund finance undrawn ($bn)', NUM, 'in'),
 ('abf_d', 'ABF / SE residual drawn ($bn)', NUM, 'in'), ('abf_u', 'ABF / SE residual undrawn ($bn)', NUM, 'in'),
 ('bdc_o', 'Named-BDC facilities drawn ($bn)', NUM, 'f'), ('bdc_c', 'Named-BDC facilities committed ($bn)', NUM, 'f'),
 ('blr_d', 'Generic back-leverage drawn ($bn)', NUM, 'f'), ('blr_u', 'Generic back-leverage undrawn ($bn)', NUM, 'f'),
 ('srt_bp', 'SRT CET1 relief (bp)', NUM, 'in'), ('pb', 'Prime / margin lending ($bn)', NUM, 'in'), ('trs', 'Written sub-IG TRS ($bn)', NUM, 'in'),
 ('ins_fac', 'Facilities to insurers ($bn)', NUM, 'in'), ('ins_repo', 'FA-backed repo ($bn)', NUM, 'in'), ('cre', 'CRE loans ($bn)', NUM, 'in'),
 ('hqla', 'HQLA ($bn)', NUM, 'in'), ('lcr', 'LCR', PCT, 'in'), ('unins', 'Uninsured / wholesale deposits ($bn)', NUM, 'in'),
 ('deposits', 'Total deposits ($bn)', NUM, 'in'), ('stwf', 'ST unsecured wholesale ($bn)', NUM, 'in'), ('repo_liab', 'Repo + sec. loaned ($bn)', NUM, 'in'),
 ('ng_share', 'Non-govt share of repo', PCT, 'in'), ('repo_ng', 'Non-govt repo funding ($bn)', NUM, 'f'),
 ('mmf_cp', 'Prime-MMF CP/CD ($bn)', NUM, 'in'), ('mmf_rep_oth', 'MMF repo, other collateral ($bn)', NUM, 'in'),
 ('cb_cap', 'CB-eligible capacity ($bn)', NUM, 'in'),
] + [(f'dg{n}', f'Downgrade outflow {n} notch ($bn)', NUM2, 'in') for n in range(7)] + [
 ('ifs_a', 'Intra-fin. assets ($bn)', NUM, 'in'), ('ifs_l', 'Intra-fin. liabilities ($bn)', NUM, 'in'), ('r0', 'CET1 ratio now', PCT2, 'f'),
 ('sale_tot', 'Saleable non-HQLA holdings ($bn)', NUM, 'f'),
]
