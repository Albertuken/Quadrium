import os
import pandas as pd
import numpy as np 

s=np.random.rand(1,10) #s0
rgeo=['UKM2','UKM3','UKM5','UKM6']

mu, sigma = 0, 0.2 # mean and standard deviation
I=np.ones([10,10])

path='/Users/ceri/Documents/Research/OMPTEC/test_code/MRIO-main/Code'

# ==============================================

os.chdir(path+'/SRIO/2008')
data_0=pd.read_excel(rgeo[0]+'.xlsx',index_col=0)
data_1=pd.read_excel(rgeo[1]+'.xlsx',index_col=0)
data_2=pd.read_excel(rgeo[2]+'.xlsx',index_col=0)
data_3=pd.read_excel(rgeo[3]+'.xlsx',index_col=0)
data=data_0+data_1+data_2+data_3

Z=data.iloc[0:10,:].iloc[:,0:10]
X=data.loc['OUTPUT'][0:10]
Y=X-Z.sum(axis=1)
F=s*np.array(X)
A=np.zeros([10,10])
for i in range(10):
    A[:,i]=Z.iloc[:,i]/X.iloc[i]
A=pd.DataFrame(A)

mu, sigma = 0, 0.3 # mean and standard deviation
# E_z=np.random.normal(mu, sigma, size=(10, 10))
# E_y=np.random.normal(mu, sigma, size=(10, ))
# E_f=np.random.normal(mu, sigma, size=(10, ))
I=np.ones([10,10])

Clist_0=[]
for t in range(1000):
    E_z=np.random.normal(mu, sigma, size=(10, 10))
    E_y=np.random.normal(mu, sigma, size=(10, ))
    E_f=np.random.normal(mu, sigma, size=(10, ))
    Z=Z+E_z
    Y=Y+E_y
    F=F+E_f
    X=Z.sum(axis=1)+Y
    for i in range(10):
        s[0][i]=F[0][i]/X[i]
    C=np.dot(s[0],(np.linalg.inv(I-A))).dot(Y)
    Clist_0.append(C)
np.std(Clist_0)/np.mean(Clist_0)

# ===================================================


os.chdir(path+'/Technical validation/Scotland')
fin=pd.read_excel('sector_index_column.xlsx',sheet_name='IxI_2008')
sector_index=pd.read_excel('sector_index_column.xlsx',sheet_name='sector_index_total',header=None)
sector_columns=sector_index
fin.index=list(range(len(fin)))
fin=fin.assign(nace=list(sector_index[0]))
agg_fin=fin.groupby(['nace']).sum()
agg_fin=agg_fin.T
agg_fin=agg_fin.assign(nace_=list(sector_columns[0]))
agg_fin=agg_fin.groupby(['nace_']).sum()
target_sum=agg_fin

Z=target_sum.iloc[0:10,:].iloc[:,0:10]
X=target_sum.loc['Total'][0:10]
Y=X-Z.sum(axis=1)
F=s*np.array(X)
A=np.zeros([10,10])
for i in range(10):
    A[:,i]=Z.iloc[:,i]/X.iloc[i]
A=pd.DataFrame(A)

Clist_1=[]
for t in range(1000):
    E_z=np.random.normal(mu, sigma, size=(10, 10))
    E_y=np.random.normal(mu, sigma, size=(10, ))
    E_f=np.random.normal(mu, sigma, size=(10, ))
    Z=Z+E_z
    Y=Y+E_y
    F=F+E_f
    X=Z.sum(axis=1)+Y
    for i in range(10):
        s[0][i]=F[0][i]/X[i]
    C=np.dot(s[0],(np.linalg.inv(I-A))).dot(Y)
    Clist_1.append(C)
np.std(Clist_1)/np.mean(Clist_1)


