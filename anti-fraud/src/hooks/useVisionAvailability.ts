import {useEffect,useState,useCallback} from 'react';
import {api} from '../services/api';

export function useVisionAvailability(){
  const [available,setAvailable]=useState(false);
  const [notice,setNotice]=useState('正在检查图片模型配置…');
  const refresh=useCallback(async()=>{
    try{
      const health=await api.health();
      if(health.provider==='school'){
        setAvailable(health.model_ready);setNotice('图片将发送给学校模型进行识别；视觉能力待校内实测。服务不支持图片时会明确失败，不生成替代结论。');
      }else{
        setAvailable(health.model_ready);
        setNotice(health.model_ready?'将使用当前配置的模型：'+health.model+'；选择远程提供方时，图片内容会发往该服务。':'当前模型不可用，请检查后端与模型配置。');
      }
    }catch{setAvailable(false);setNotice('尚未连接反诈后端，请启动后重新检查。');}
  },[]);
  useEffect(()=>{void refresh()},[refresh]);
  return {available,notice,refresh};
}
