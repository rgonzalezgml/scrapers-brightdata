# Modelos Semánticos — Mapeo YAML → Vista

| Modelo YAML | Base de datos | Schema | Vista |
|---|---|---|---|
| `semantic_oliveyoung_rank.yaml` | `PRD_CNS_SHD` | `DATA_GNM` | `VW_OLIVEYOUNG_RANK_HIST` |
| `semantic_oliveyoung_newarrivals.yaml` | `PRD_CNS_SHD` | `DATA_GNM` | `VW_OLIVEYOUNG_NEWARRIVALS` |
| `semantic_cosme_ranking.yaml` | `PRD_CNS_SHD` | `DATA_GNM` | `VW_COSME_RANKING_HIST` |
| `semantic_cosme_newarrivals.yaml` | `PRD_CNS_SHD` | `DATA_GNM` | `VW_COSME_RANKING_NEWARRIVALS` |
| `semantic_alibaba_prov.yaml` | `PRD_CNS_SHD` | `DATA_GNM` | `VW_ALIBABA_PROV_HIST` |
| `semantic_indiamart_prov.yaml` | `PRD_CNS_SHD` | `DATA_GNM` | `VW_INDIAMART_PROV_HIST` |
| `semantic_madeinchina_prov.yaml` | `PRD_CNS_SHD` | `DATA_GNM` | `VW_MADEINCHINA_PROV_HIST` |
| `semantic_cosmetic_design_articulos.yaml` | `PRD_CNS_SHD` | `DATA_GNM` | `VW_COSMETIC_DESIGN_ARTICULOS` |

## Estado de las vistas en producción

| Vista | Estado |
|---|---|
| `VW_OLIVEYOUNG_RANK_HIST` | ✅ Existe |
| `VW_COSME_RANKING_HIST` | ✅ Existe |
| `VW_COSMETIC_DESIGN_ARTICULOS` | ✅ Existe |
| `VW_OLIVEYOUNG_NEWARRIVALS` | ⏳ Pendiente (`vistas.sql`) |
| `VW_COSME_RANKING_NEWARRIVALS` | ⏳ Pendiente (`vistas.sql`) |
| `VW_ALIBABA_PROV_HIST` | ⏳ Pendiente (`vistas.sql`) |
| `VW_INDIAMART_PROV_HIST` | ⏳ Pendiente (`vistas.sql`) |
| `VW_MADEINCHINA_PROV_HIST` | ⏳ Pendiente (`vistas.sql`) |



Cada archivo YAML ya tiene configurada la vista que debe
  consumir:                                                                                                                             
                                                            
  📊 Olive Young                                                                                                                        
  • semantic_oliveyoung_rank.yaml → VW_OLIVEYOUNG_RANK_HIST                                                                             
  • semantic_oliveyoung_newarrivals.yaml → VW_OLIVEYOUNG_NEWARRIVALS                                                                    
                                                                                                                                        
  📊 @cosme Japón                                                                                                                       
  • semantic_cosme_ranking.yaml → VW_COSME_RANKING_HIST     
  • semantic_cosme_newarrivals.yaml → VW_COSME_RANKING_NEWARRIVALS

  📊 Proveedores B2B                                                                                                                    
  • semantic_alibaba_prov.yaml → VW_ALIBABA_PROV_HIST
  • semantic_indiamart_prov.yaml → VW_INDIAMART_PROV_HIST                                                                               
  • semantic_madeinchina_prov.yaml → VW_MADEINCHINA_PROV_HIST                                                                           
   
  📊 Noticias                                                                                                                           
  • semantic_cosmetic_design_articulos.yaml → VW_COSMETIC_DESIGN_ARTICULOS
                                                                                                                                        
  Todas las vistas viven en PRD_CNS_SHD.DATA_GNM. Las 3 primeras (OliveYoung rank, cosme ranking y cosmetic design) ya existen. Las 5   
  restantes quedan pendientes de crear con el DDL de vistas.sql.                                                                        
                                                                                                                                        
✻ Crunched for 6s                                           

❯ porne db y squema                                                                                                                     
                                  
● Aquí tienes:                                                                                                                          
                                                            
  ---                                                                                                                                   
  Hola! 👋 Comparto el detalle de los modelos semánticos para Cortex Analyst. Cada archivo YAML ya tiene configurada la vista que debe
  consumir:                                                                                                                             
                                                            
  📊 Olive Young
  • semantic_oliveyoung_rank.yaml → PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_RANK_HIST
  • semantic_oliveyoung_newarrivals.yaml → PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_NEWARRIVALS                                               
                                                                                                                                        
  📊 @cosme Japón                                                                                                                       
  • semantic_cosme_ranking.yaml → PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_HIST                                                            
  • semantic_cosme_newarrivals.yaml → PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_NEWARRIVALS                                                 
                                                                                                                                        
  📊 Proveedores B2B                                                                                                                    
  • semantic_alibaba_prov.yaml → PRD_CNS_SHD.DATA_GNM.VW_ALIBABA_PROV_HIST                                                              
  • semantic_indiamart_prov.yaml → PRD_CNS_SHD.DATA_GNM.VW_INDIAMART_PROV_HIST                                                          
  • semantic_madeinchina_prov.yaml → PRD_CNS_SHD.DATA_GNM.VW_MADEINCHINA_PROV_HIST                                                      
                                                                                                                                        
  📊 cosmetic_design                                                                                                                           
  • semantic_cosmetic_design_articulos.yaml → PRD_CNS_SHD.DATA_GNM.VW_COSMETIC_DESIGN_ARTICULOS