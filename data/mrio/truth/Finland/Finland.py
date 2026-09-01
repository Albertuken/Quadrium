import os
import pandas as pd
import numpy as np
from scipy.stats import pearsonr
path="/Users/ceri/Documents/Research/OMPTEC/test_code/MRIO-main/Code"
os.chdir(path+'/Technical validation/Finland')

col_names = ['rgeo','MAD','DISM','corr','p']
fin_nuts2=['FI19','FI20','FI1B','FI1C','FI1D']
corr_result=[]
df_corr = pd.DataFrame(corr_result,columns=col_names)

for n in range(5):
    os.chdir(path+'/Technical validation/Finland')
    fin=pd.read_excel('io_reg_2014.xlsx',sheet_name=fin_nuts2[n])
    sector_index=pd.read_excel('sector_index_column.xlsx',sheet_name=0,header=None)
    sector_columns=pd.read_excel('sector_index_column.xlsx',sheet_name=1,header=None)
    fin.index=list(range(len(fin)))
    fin=fin.assign(nace=list(sector_index[0]))
    agg_fin=fin.groupby(['nace']).sum()
    agg_fin=agg_fin.T
    agg_fin=agg_fin.assign(nace_=list(sector_columns[0]))
    agg_fin=agg_fin.groupby(['nace_']).sum()
    agg_fin=agg_fin.T.iloc[0:10].iloc[:,0:11]
    target_sum=agg_fin.drop(['FD'],axis=1)
     
    os.chdir(path+'/SRIO/2014')
    fi1b=pd.read_excel(fin_nuts2[n]+'.xlsx',index_col=0)
    ours_sum=fi1b.iloc[0:10,:].iloc[:,0:10]
    
    MAD=abs(ours_sum-target_sum).mean().mean()
    DISM=(abs(ours_sum-target_sum)/(ours_sum+target_sum+0.0001)/2).mean().mean()
    
    data1=np.array(target_sum).reshape(10*10,)
    data2=np.array(ours_sum).reshape(10*10,)
    corr,p=pearsonr(data1,data2)
    
    new_data = pd.DataFrame({'rgeo':fin_nuts2[n],'MAD':MAD,'DISM':DISM,'corr':corr,'p':p},index=[str(n)]) 
    df_corr = pd.concat([df_corr,new_data],axis=0)   
os.chdir(path+'/Technical validation/Finland')
df_corr.to_excel('df_corr.xlsx')   



