import os
import pandas as pd
import numpy as np 

s=np.random.rand(1,10) #s0
rgeo=['FI19','FI20','FI1B','FI1C','FI1D']

mu, sigma = 0, 0.2 # mean and standard deviation
I=np.ones([10,10])
path='/Users/ceri/Documents/Research/OMPTEC/test_code/MRIO-main/Code'

# =======================================================
C_finland_0=[]
for n in range(len(rgeo)):
    path="/Users/ceri/Documents/Research/OMPTEC/test_code/MRIO-main/Code"
    os.chdir(path+"/SRIO/2014")
    fi1b=pd.read_excel(rgeo[n]+'.xlsx',index_col=0)
    Z=data.iloc[0:10,:].iloc[:,0:10]
    X=data.loc['OUTPUT'][0:10]
    Y=X-Z.sum(axis=1)
    F=s*np.array(X)
    A=np.zeros([10,10])
    for i in range(10):
        A[:,i]=Z.iloc[:,i]/X.iloc[i]
    A=pd.DataFrame(A)

    mu, sigma = 0, 0.3 # mean and standard deviation
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
    C_finland_0.append(np.std(Clist_0)/np.mean(Clist_0))
os.chdir(path+'/Technical validation')
pd.DataFrame(C_finland_0,index=rgeo).to_excel('Finland_MRIO_sig'+str(sigma)+'.xlsx')


# ========================================================

C_finland_1=[]
for n in range(len(rgeo)):
    path="/Users/ceri/Documents/Research/OMPTEC/test_code/MRIO-main/Code"
    os.chdir(path+'/Technical validation/Finland')
    fin=pd.read_excel('io_reg2014.xlsx',sheet_name=rgeo[n])
    sector_index=pd.read_excel('sector.xlsx',sheet_name=0,header=None)
    sector_columns=pd.read_excel('sector.xlsx',sheet_name=1,header=None)
    fin.index=list(range(len(fin)))
    fin=fin.assign(nace=list(sector_index[0]))
    agg_fin=fin.groupby(['nace']).sum()
    agg_fin=agg_fin.T
    agg_fin=agg_fin.assign(nace_=list(sector_columns[0]))
    agg_fin=agg_fin.groupby(['nace_']).sum()
    agg_fin=agg_fin.T
    agg_fin=agg_fin.drop(['FD'],axis=1)
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
    C_finland_1.append(np.std(Clist_1)/np.mean(Clist_1))
os.chdir(path+'/Technical validation')
pd.DataFrame(C_finland_1,index=rgeo).to_excel('Finland_null_sig'+str(sigma)+'.xlsx')

