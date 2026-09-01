import os
import pandas as pd
import numpy as np
from scipy.stats import pearsonr
path="/Users/ceri/Documents/Research/OMPTEC/test_code/MRIO-main/Code"
os.chdir(path+'/Technical validation/Scotland')
rgeo=['UKM2','UKM3','UKM5','UKM6']
fin=pd.read_excel('sector_index_column.xlsx',sheet_name='IxI_2008')
sector_index=pd.read_excel('sector_index_column.xlsx',sheet_name='sector_index_total',header=None)
sector_columns=sector_index
fin.index=list(range(len(fin)))
fin=fin.assign(nace=list(sector_index[0]))
agg_fin=fin.groupby(['nace']).sum()
agg_fin=agg_fin.T
agg_fin=agg_fin.assign(nace_=list(sector_columns[0]))
agg_fin=agg_fin.groupby(['nace_']).sum()
target_sum=agg_fin.iloc[0:10,:].iloc[:,0:10]

os.chdir(path+'/SRIO/2008')
data_0=pd.read_excel(rgeo[0]+'.xlsx',index_col=0)
data_1=pd.read_excel(rgeo[1]+'.xlsx',index_col=0)
data_2=pd.read_excel(rgeo[2]+'.xlsx',index_col=0)
data_3=pd.read_excel(rgeo[3]+'.xlsx',index_col=0)
data=data_0+data_1+data_2+data_3
ours_sum=data.iloc[0:10,:].iloc[:,0:10]
MAD=abs(ours_sum-target_sum).mean().mean()
DISM=(abs(ours_sum-target_sum)/(ours_sum+target_sum+0.0001)/2).mean().mean()
    
data1=np.array(target_sum).reshape(10*10,)
data2=np.array(ours_sum).reshape(10*10,)
print('MAD:'+str(MAD))
print('DISM'+str(DISM))
print(pearsonr(data1,data2))