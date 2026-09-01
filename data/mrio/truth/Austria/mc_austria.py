import os
import pandas as pd
import numpy as np 

s=np.random.rand(1,10) #s0
rgeo=['AT11','AT12','AT13','AT21','AT22','AT31','AT32','AT33','AT34']

mu, sigma = 0, 0.2 # mean and standard deviation
I=np.ones([10,10])


# ======================================================
C_austria_0=[]
for n in range(len(rgeo)):
    path="/Users/ceri/Documents/Research/OMPTEC/test_code/MRIO-main/Code"
    os.chdir(path+"/SRIO/2011")
    data=pd.read_excel(rgeo[n]+'.xlsx',index_col=0)
    Z=data.iloc[0:10,:].iloc[:,0:10]
    X=data.loc['OUTPUT'][0:10]
    Y=X-Z.sum(axis=1)
    F=s*np.array(X)
    A=np.zeros([10,10])
    for i in range(10):
        A[:,i]=Z.iloc[:,i]/X.iloc[i]
    A=pd.DataFrame(A)



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
    C_austria_0.append(np.std(Clist_0)/np.mean(Clist_0))
os.chdir(path+'/Technical validation')
pd.DataFrame(C_austria_0,index=rgeo).to_excel('Austria_MRIO_sig'+str(sigma)+'.xlsx')




# ==========================================================
C_austria_1=[]
for n in range(len(rgeo)):
    path="/Users/ceri/Documents/Research/OMPTEC/test_code/MRIO-main/Code"
    os.chdir(path+'/Technical validation/Austria')
    ref_=pd.read_csv(rgeo[n]+'.csv',index_col=0)
    ref=ref_.iloc[0:68,:].iloc[:,0:59]
    sector_index=pd.read_excel('sector_index_column.xlsx',sheet_name=3)
    sector_columns=pd.read_excel('sector_index_column.xlsx',sheet_name=3)
    Total_x=list(ref_.iloc[72,:].iloc[0:59])
    Total_x.append(0)
    ref=ref.assign(Total=list(ref_['Total'].iloc[0:68]))
    # agg_fin=ref.groupby(['nace']).sum()
    ref=ref.T
    ref=ref.assign(Total=Total_x)
    ref=ref.T

    ref.index=list(range(len(ref)))
    ref=ref.assign(nace=list(sector_index['NACE']))
    agg_fin=ref.groupby(['nace']).sum()
    agg_fin=agg_fin.T
    agg_fin=agg_fin.assign(nace_=list(sector_columns['NACE']))
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
    C_austria_1.append(np.std(Clist_1)/np.mean(Clist_1))
os.chdir(path+'/Technical validation')
pd.DataFrame(C_austria_1,index=rgeo).to_excel('Austria_null_sig'+str(sigma)+'.xlsx')