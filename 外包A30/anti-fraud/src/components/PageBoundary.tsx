import { Component, type ReactNode } from 'react';

/** Recover a failed page chunk/render without pretending a request completed. */
export default class PageBoundary extends Component<{children:ReactNode;page:string},{failed:boolean}> {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  componentDidUpdate(previous:{page:string}) {
    if(previous.page!==this.props.page && this.state.failed)this.setState({failed:false});
  }
  render(){
    if(this.state.failed)return <section className="panel" role="alert"><h2>这个页面暂时没有加载完成</h2><p>可以切换其他页面，或刷新重试。已有后端分析记录不会因此变成已完成或被删除。</p><button className="button" onClick={()=>window.location.reload()}>刷新页面</button></section>;
    return this.props.children;
  }
}
