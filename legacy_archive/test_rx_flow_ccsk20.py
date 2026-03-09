import yaml
with open('mission_configs/level7_ofdm_master.yaml', 'r') as f:
    cfg = yaml.safe_load(f)
print("Config frame_size:", cfg['link_layer'].get('frame_size'))
print("Config use_ccsk:", cfg.get('dsss', {}).get('enabled'))
print("Config use_comsec:", cfg['link_layer'].get('use_comsec'))
print("Config comsec_key:", cfg['link_layer'].get('comsec_key'))
