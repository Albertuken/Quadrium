import pandas as pd
import numpy as np
import os
from scipy.stats import pearsonr
path="/Users/ceri/Documents/Research/OMPTEC/test_code/MRIO-main/Code"
os.chdir(path+'/Technical validation/Austria')

col_names = ['rgeo','MAD','DISM','corr','p']
corr_result=[]
df_corr = pd.DataFrame(corr_result,columns=col_names)
rgeo=['AT11','AT12','AT13','AT21','AT22','AT31','AT32','AT33','AT34']
for n in range(len(rgeo)):
    os.chdir(path+'/Technical validation/Austria')
    ref=pd.read_csv(rgeo[n]+'.csv',index_col=0)
    ref=ref.iloc[0:68,:].iloc[:,0:59]
    sector_index=pd.read_excel('sector_index_column.xlsx',sheet_name=0)
    sector_columns=pd.read_excel('sector_index_column.xlsx',sheet_name=1)
    ref.index=list(range(len(ref)))
    ref=ref.assign(nace=list(sector_index['NACE']))
    agg_fin=ref.groupby(['nace']).sum()
    agg_fin=agg_fin.T
    agg_fin=agg_fin.assign(nace_=list(sector_columns['NACE']))
    agg_fin=agg_fin.groupby(['nace_']).sum()
    target_sum=agg_fin
     
    os.chdir(path+"/SRIO/2011")
    fi1b=pd.read_excel(rgeo[n]+'.xlsx',index_col=0)
    ours_sum=fi1b.iloc[0:10,:].iloc[:,0:10]
    
    MAD=abs(ours_sum-target_sum).mean().mean()
    DISM=(abs(ours_sum-target_sum)/(ours_sum+target_sum+0.0001)/2).mean().mean()
    
    data1=np.array(target_sum).reshape(10*10,)
    data2=np.array(ours_sum).reshape(10*10,)
    corr,p=pearsonr(data1,data2)
    
    new_data = pd.DataFrame({'rgeo':rgeo[n],'MAD':MAD,'DISM':DISM,'corr':corr,'p':p},index=[str(n)]) 
    df_corr = pd.concat([df_corr,new_data],axis=0)   
os.chdir(path+'/Technical validation/Austria')
df_corr.to_excel('df_corr.xlsx')